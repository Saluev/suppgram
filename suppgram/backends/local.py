from datetime import datetime, timezone
from typing import List, Iterable, Any

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
)
from suppgram.errors import PermissionDenied
from suppgram.helpers import flat_gather
from suppgram.observer import LocalObservable
from suppgram.permissions import Permission, Decision, PermissionChecker
from suppgram.storage import Storage
from suppgram.texts.en import EnglishTexts
from suppgram.texts.interface import Texts


class LocalBackend(BackendInterface):
    def __init__(
        self,
        storage: Storage,
        permission_checkers: List[PermissionChecker],
        workplace_managers: List[WorkplaceManager],
        texts: Texts = EnglishTexts(),
    ):
        self._storage = storage
        self._permission_checkers = permission_checkers
        self._workplace_managers = workplace_managers
        self._texts = texts

        self.on_new_conversation = LocalObservable[ConversationEvent]()
        self.on_conversation_assignment = LocalObservable[ConversationEvent]()
        self.on_conversation_resolution = LocalObservable[ConversationEvent]()
        self.on_new_message_for_customer = LocalObservable[NewMessageForCustomerEvent]()
        self.on_new_unassigned_message_from_customer = LocalObservable[
            NewUnassignedMessageFromCustomerEvent
        ]()
        self.on_new_message_for_agent = LocalObservable[NewMessageForAgentEvent]()

    async def create_agent(self, identification: AgentIdentification) -> Agent:
        return await self._storage.create_agent(identification)

    async def identify_agent(self, identification: AgentIdentification) -> Agent:
        return await self._storage.get_agent(identification)

    async def update_agent(self, identification: AgentIdentification, diff: AgentDiff):
        return await self._storage.update_agent(identification, diff)

    async def identify_customer_conversation(
        self, identification: CustomerIdentification
    ) -> Conversation:
        customer = await self._storage.get_or_create_customer(identification)
        conversation = await self._storage.get_or_create_conversation(customer)
        return conversation

    async def identify_workplace(
        self, identification: WorkplaceIdentification
    ) -> Workplace:
        agent = await self._storage.get_agent(identification.to_agent_identification())
        workplace = await self._storage.get_or_create_workplace(agent, identification)
        return workplace

    def check_permission(self, agent: Agent, permission: Permission) -> bool:
        return self._sum_decisions(
            checker.check_permission(agent, permission)
            for checker in self._permission_checkers
        )

    def _sum_decisions(self, decisions: Iterable[Decision]) -> bool:
        has_been_allowed = False
        has_been_denied = False
        for decision in decisions:
            if decision == Decision.ALLOWED:
                has_been_allowed = True
            if decision == Decision.DENIED:
                has_been_denied = True
        return has_been_allowed and not has_been_denied

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

    async def _process_message_from_user(
        self, conversation: Conversation, message: Message
    ):
        await self._storage.save_message(conversation, message)
        conversation.messages.append(message)
        if len(conversation.messages) == 1:
            await self.on_new_conversation.trigger(ConversationEvent(conversation))
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
                NewUnassignedMessageFromCustomerEvent(
                    message=message, conversation=conversation
                )
            )

    async def _process_message_from_agent(
        self, conversation: Conversation, message: Message
    ):
        await self._storage.save_message(conversation, message)
        await self.on_new_message_for_customer.trigger(
            NewMessageForCustomerEvent(customer=conversation.customer, message=message)
        )

    async def _process_internal_message(
        self, conversation: Conversation, message: Message
    ):
        await self._storage.save_message(conversation, message)
        await self.on_new_message_for_customer.trigger(
            NewMessageForCustomerEvent(customer=conversation.customer, message=message)
        )
        if conversation.assigned_agent and conversation.assigned_workplace:
            await self.on_new_message_for_agent.trigger(
                NewMessageForAgentEvent(
                    agent=conversation.assigned_agent,
                    workplace=conversation.assigned_workplace,
                    message=message,
                )
            )

    async def assign_agent(
        self, assigner: Agent, assignee: Agent, conversation_id: Any
    ):
        permission = (
            Permission.ASSIGN_TO_SELF
            if assigner == assignee
            else Permission.ASSIGN_TO_OTHERS
        )
        if not self.check_permission(assigner, permission):
            raise PermissionDenied("not allowed to assign conversation to this agent")

        workplace = await self._choose_workplace(assignee)
        await self._storage.update_conversation(
            conversation_id,
            ConversationDiff(
                state=ConversationState.ASSIGNED, assigned_workplace_id=workplace.id
            ),
            unassigned_only=True,
        )
        conversation = await self._storage.get_agent_conversation(workplace)
        await self.on_conversation_assignment.trigger(
            ConversationEvent(conversation=conversation)
        )
        await self.on_new_message_for_agent.trigger_batch(
            [
                NewMessageForAgentEvent(
                    agent=assignee, workplace=workplace, message=message
                )
                for message in conversation.messages
            ]
        )

    async def resolve_conversation(self, resolver: Agent, conversation: Conversation):
        if resolver != conversation.assigned_agent:
            raise PermissionDenied(
                "not allowed to resolve conversations of other agents"
            )

        # TODO processing message and updating conversation should be in a single transaction
        await self.process_message(
            conversation,
            Message(kind=MessageKind.RESOLVED, time_utc=datetime.now(timezone.utc)),
        )
        await self._storage.update_conversation(
            conversation.id,
            ConversationDiff(
                state=ConversationState.RESOLVED, assigned_workplace_id=SetNone
            ),
        )
        conversation = Conversation(
            id=conversation.id,
            state=ConversationState.RESOLVED,
            customer=conversation.customer,
            messages=conversation.messages,
        )
        await self.on_conversation_resolution.trigger(
            ConversationEvent(conversation=conversation)
        )

    async def _choose_workplace(self, agent: Agent) -> Workplace:
        existing_workplaces = await self._storage.get_agent_workplaces(agent)
        extra_workplaces = await self._create_all_missing_workplaces(
            agent, existing_workplaces
        )
        all_workplaces = existing_workplaces + extra_workplaces
        available_workplaces = await self._filter_all_available_workplaces(
            all_workplaces
        )
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
                        agent, workplace_identification
                    )
                    for workplace_identification in missing_workplace_identifications
                )
            )
        return extra_workplaces

    async def _filter_all_available_workplaces(
        self, all_workplaces: List[Workplace]
    ) -> List[Workplace]:
        available_workplaces: List[Workplace] = []
        for manager in self._workplace_managers:
            available_workplaces.extend(
                manager.filter_available_workplaces(all_workplaces)
            )
        return available_workplaces