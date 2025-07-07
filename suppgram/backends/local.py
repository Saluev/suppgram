from datetime import datetime, timezone
from typing import List, Any, Optional

from suppgram.backend import Backend as BackendInterface, WorkplaceManager
from suppgram.entities import (
    ConversationEvent,
    NewMessageForCustomerEvent,
    NewUnassignedMessageFromCustomerEvent,
    NewMessageForAgentEvent,
    AgentIdentification,
    Agent,
    AgentDiff,
    CustomerIdentification,
    Conversation,
    WorkplaceIdentification,
    Workplace,
    Message,
    ConversationState,
    ConversationDiff,
    SetNone,
    MessageKind,
    CustomerDiff,
    Tag,
    ConversationTagEvent,
    Customer,
    TagEvent,
    Event,
    EventKind,
)
from suppgram.errors import PermissionDenied, AgentDeactivated
from suppgram.helpers import flat_gather
from suppgram.observer import LocalObservable
from suppgram.storage import Storage
from suppgram.texts.en import EnglishTextProvider
from suppgram.texts.interface import TextProvider


class LocalBackend(BackendInterface):
    def __init__(
        self,
        storage: Storage,
        workplace_managers: List[WorkplaceManager],
        texts: TextProvider = EnglishTextProvider(),
    ):
        self._storage = storage
        self._workplace_managers = workplace_managers
        self._texts = texts

        self.on_new_conversation = LocalObservable[ConversationEvent]()
        self.on_conversation_assignment = LocalObservable[ConversationEvent]()
        self.on_conversation_resolution = LocalObservable[ConversationEvent]()
        self.on_conversation_tag_added = LocalObservable[ConversationTagEvent]()
        self.on_conversation_tag_removed = LocalObservable[ConversationTagEvent]()
        self.on_conversation_rated = LocalObservable[ConversationEvent]()
        self.on_new_message_for_customer = LocalObservable[NewMessageForCustomerEvent]()
        self.on_new_unassigned_message_from_customer = LocalObservable[
            NewUnassignedMessageFromCustomerEvent
        ]()
        self.on_new_message_for_agent = LocalObservable[NewMessageForAgentEvent]()
        self.on_tag_created = LocalObservable[TagEvent]()

    async def create_or_update_agent(
        self, identification: AgentIdentification, diff: Optional[AgentDiff] = None
    ) -> Agent:
        agent = await self._storage.create_or_update_agent(identification, diff)
        existing_workplaces = await self._storage.get_agent_workplaces(agent)
        await self._create_all_missing_workplaces(agent, existing_workplaces)
        return agent

    async def identify_agent(self, identification: AgentIdentification) -> Agent:
        return await self._storage.get_agent(identification)

    async def update_agent(self, identification: AgentIdentification, diff: AgentDiff) -> Agent:
        if diff.deactivated:
            raise ValueError("can't deactivate agent via diff, use `deactivate_agent()`")
        return await self._storage.update_agent(identification, diff)

    async def deactivate_agent(self, agent: Agent):
        # TODO transaction?..
        conversations = await self._storage.find_agent_conversations(agent)
        await flat_gather(self.postpone_conversation(agent, conv) for conv in conversations)
        await self._storage.update_agent(agent.identification, AgentDiff(deactivated=True))

    async def create_or_update_customer(
        self, identification: CustomerIdentification, diff: Optional[CustomerDiff] = None
    ) -> Customer:
        return await self._storage.create_or_update_customer(identification, diff)

    async def identify_customer_conversation(
        self, identification: CustomerIdentification
    ) -> Conversation:
        customer = await self._storage.create_or_update_customer(identification)
        conversation = await self._storage.get_or_create_conversation(customer)
        return conversation

    async def identify_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        return await self._storage.get_or_create_workplace(identification)

    async def create_tag(self, name: str, created_by: Agent) -> Tag:
        if created_by.deactivated:
            raise AgentDeactivated(created_by.identification)

        tag = await self._storage.create_tag(name=name, created_by=created_by)
        await self.on_tag_created.trigger(TagEvent(tag=tag))
        return tag

    async def get_all_tags(self) -> List[Tag]:
        return await self._storage.find_all_tags()

    async def identify_agent_conversation(
        self, identification: WorkplaceIdentification
    ) -> Conversation:
        return await self._storage.get_agent_conversation(identification)

    async def process_message(self, conversation: Conversation, message: Message):
        if message.kind == MessageKind.FROM_CUSTOMER:
            await self._process_message_from_user(conversation, message)
        elif message.kind == MessageKind.FROM_AGENT:
            await self._process_message_from_agent(conversation, message)
        else:
            await self._process_internal_message(conversation, message)

    async def _process_message_from_user(self, conversation: Conversation, message: Message):
        await self._storage.save_message(conversation, message)
        conversation.messages.append(message)
        if len(conversation.messages) == 1:
            await self.on_new_conversation.trigger(ConversationEvent(conversation))
            await self._storage.save_event(
                Event(
                    kind=EventKind.CONVERSATION_STARTED,
                    time_utc=message.time_utc,
                    conversation_id=conversation.id,
                    customer_id=conversation.customer.id,
                )
            )
        if conversation.assigned_agent and conversation.assigned_workplace:
            await self.on_new_message_for_agent.trigger(
                NewMessageForAgentEvent(
                    agent=conversation.assigned_agent,
                    workplace=conversation.assigned_workplace,
                    message=message,
                )
            )
        else:
            await self.on_new_unassigned_message_from_customer.trigger(
                NewUnassignedMessageFromCustomerEvent(message=message, conversation=conversation)
            )
        await self._storage.save_event(
            Event(
                kind=EventKind.MESSAGE_SENT,
                time_utc=message.time_utc,
                conversation_id=conversation.id,
                customer_id=conversation.customer.id,
                message_kind=message.kind,
                message_media_kind=message.media_kind,
            )
        )

    async def _process_message_from_agent(self, conversation: Conversation, message: Message):
        if conversation.assigned_agent and conversation.assigned_agent.deactivated:
            raise AgentDeactivated(conversation.assigned_agent.identification)

        await self._storage.save_message(conversation, message)
        await self.on_new_message_for_customer.trigger(
            NewMessageForCustomerEvent(
                conversation=conversation,
                message=message,
            )
        )
        await self._storage.save_event(
            Event(
                kind=EventKind.MESSAGE_SENT,
                time_utc=message.time_utc,
                conversation_id=conversation.id,
                customer_id=conversation.customer.id,
                message_kind=message.kind,
                message_media_kind=message.media_kind,
            )
        )

    async def _process_internal_message(self, conversation: Conversation, message: Message):
        await self._storage.save_message(conversation, message)
        await self.on_new_message_for_customer.trigger(
            NewMessageForCustomerEvent(
                conversation=conversation,
                message=message,
            )
        )
        if conversation.assigned_agent and conversation.assigned_workplace:
            await self.on_new_message_for_agent.trigger(
                NewMessageForAgentEvent(
                    agent=conversation.assigned_agent,
                    workplace=conversation.assigned_workplace,
                    message=message,
                )
            )

    async def assign_agent(self, assigner: Agent, assignee: Agent, conversation_id: Any):
        if assigner.deactivated:
            raise AgentDeactivated(assigner.identification)
        if assignee.deactivated:
            raise AgentDeactivated(assignee.identification)

        workplace = await self._choose_workplace(assignee)
        await self._storage.update_conversation(
            conversation_id,
            ConversationDiff(state=ConversationState.ASSIGNED, assigned_workplace_id=workplace.id),
            unassigned_only=True,
        )
        conversation = await self._storage.get_agent_conversation(workplace.identification)
        await self.on_conversation_assignment.trigger(ConversationEvent(conversation=conversation))
        await self._storage.save_event(
            Event(
                kind=EventKind.AGENT_ASSIGNED,
                agent_id=assignee.id,
                conversation_id=conversation.id,
                customer_id=conversation.customer.id,
            )
        )

    async def get_conversations(
        self, conversation_ids: List[Any], with_messages: bool = False
    ) -> List[Conversation]:
        return await self._storage.find_conversations_by_ids(
            conversation_ids, with_messages=with_messages
        )

    async def get_customer_conversations(self, customer: Customer) -> List[Conversation]:
        return await self._storage.find_customer_conversations(customer, with_messages=True)

    async def add_tag_to_conversation(self, conversation: Conversation, tag: Tag):
        await self._storage.update_conversation(conversation.id, ConversationDiff(added_tags=[tag]))
        conversation = await self.get_conversation(conversation.id)
        await self.on_conversation_tag_added.trigger(
            ConversationTagEvent(conversation=conversation, tag=tag)
        )
        await self._storage.save_event(
            Event(
                kind=EventKind.CONVERSATION_TAG_ADDED,
                conversation_id=conversation.id,
                customer_id=conversation.customer.id,
                tag_id=tag.id,
            )
        )

    async def remove_tag_from_conversation(self, conversation: Conversation, tag: Tag):
        await self._storage.update_conversation(
            conversation.id, ConversationDiff(removed_tags=[tag])
        )
        conversation = await self.get_conversation(conversation.id)
        await self.on_conversation_tag_removed.trigger(
            ConversationTagEvent(conversation=conversation, tag=tag)
        )
        await self._storage.save_event(
            Event(
                kind=EventKind.CONVERSATION_TAG_REMOVED,
                conversation_id=conversation.id,
                customer_id=conversation.customer.id,
                tag_id=tag.id,
            )
        )

    async def rate_conversation(self, conversation: Conversation, rating: int):
        await self._storage.update_conversation(
            conversation.id, ConversationDiff(customer_rating=rating)
        )
        conversation = await self.get_conversation(conversation.id)
        await self.on_conversation_rated.trigger(ConversationEvent(conversation=conversation))
        await self._storage.save_event(
            Event(
                kind=EventKind.CONVERSATION_RATED,
                conversation_id=conversation.id,
                customer_id=conversation.customer.id,
            )
        )

    async def postpone_conversation(self, postponer: Agent, conversation: Conversation):
        if postponer != conversation.assigned_agent:
            raise PermissionDenied("not allowed to postpone conversations of other agents")

        await self.process_message(
            conversation,
            Message(kind=MessageKind.POSTPONED, time_utc=datetime.now(timezone.utc)),
        )
        await self._storage.update_conversation(
            conversation.id,
            ConversationDiff(state=ConversationState.NEW, assigned_workplace_id=SetNone),
        )
        conversation = Conversation(  # TODO just fetch?..
            id=conversation.id,
            state=ConversationState.NEW,
            customer=conversation.customer,
            messages=conversation.messages,
            tags=conversation.tags,
        )
        await self.on_new_conversation.trigger(ConversationEvent(conversation=conversation))
        await self._storage.save_event(
            Event(
                kind=EventKind.CONVERSATION_POSTPONED,
                agent_id=postponer.id,
                conversation_id=conversation.id,
                customer_id=conversation.customer.id,
            )
        )

    async def resolve_conversation(self, resolver: Agent, conversation: Conversation):
        if resolver != conversation.assigned_agent:
            raise PermissionDenied("not allowed to resolve conversations of other agents")
        if resolver.deactivated:
            await self.postpone_conversation(resolver, conversation)
            raise AgentDeactivated(resolver.identification)

        # TODO processing message and updating conversation should be in a single transaction
        await self.process_message(
            conversation,
            Message(kind=MessageKind.RESOLVED, time_utc=datetime.now(timezone.utc)),
        )
        await self._storage.update_conversation(
            conversation.id,
            ConversationDiff(state=ConversationState.RESOLVED, assigned_workplace_id=SetNone),
        )
        conversation = Conversation(  # TODO just fetch?..
            id=conversation.id,
            state=ConversationState.RESOLVED,
            customer=conversation.customer,
            messages=conversation.messages,
            tags=conversation.tags,
        )
        await self.on_conversation_resolution.trigger(ConversationEvent(conversation=conversation))
        await self._storage.save_event(
            Event(
                kind=EventKind.CONVERSATION_POSTPONED,
                agent_id=resolver.id,
                conversation_id=conversation.id,
                customer_id=conversation.customer.id,
            )
        )

    async def _choose_workplace(self, agent: Agent) -> Workplace:
        existing_workplaces = await self._storage.get_agent_workplaces(agent)
        extra_workplaces = await self._create_all_missing_workplaces(agent, existing_workplaces)
        all_workplaces = existing_workplaces + extra_workplaces
        available_workplaces = await self._filter_all_available_workplaces(agent, all_workplaces)
        return available_workplaces[0]  # TODO handle index out of range

    async def _create_all_missing_workplaces(
        self, agent: Agent, existing_workplaces: List[Workplace]
    ) -> List[Workplace]:
        extra_workplaces: List[Workplace] = []
        for manager in self._workplace_managers:
            missing_workplace_identifications = manager.create_missing_workplaces(
                agent, existing_workplaces
            )
            extra_workplaces.extend(
                await flat_gather(
                    self._storage.get_or_create_workplace(  # TODO session/batch
                        workplace_identification
                    )
                    for workplace_identification in missing_workplace_identifications
                )
            )
        return extra_workplaces

    async def _filter_all_available_workplaces(
        self, agent: Agent, all_workplaces: List[Workplace]
    ) -> List[Workplace]:
        available_workplaces: List[Workplace] = []
        for manager in self._workplace_managers:
            available_workplaces.extend(
                manager.filter_and_rank_available_workplaces(all_workplaces)
            )
        agent_conversations = await self._storage.find_agent_conversations(agent)
        busy_workplace_ids = {
            conv.assigned_workplace.id
            for conv in agent_conversations
            if conv.assigned_workplace  # it can't be None, but for the sake of typing let's check
        }
        free_workplaces = [
            workplace
            for workplace in available_workplaces
            if workplace.id not in busy_workplace_ids
        ]
        return free_workplaces
