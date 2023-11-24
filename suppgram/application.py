from typing import List, Iterable, Any

from suppgram.entities import (
    UserIdentification,
    Agent,
    WorkplaceIdentification,
    Workplace,
    Message,
    Conversation,
    NewConversationEvent,
    NewMessageForUserEvent,
    NewMessageForAgentEvent,
    AgentIdentification,
    NewUnassignedMessageFromUserEvent,
    AgentDiff,
)
from suppgram.errors import PermissionDenied
from suppgram.helpers import flat_gather
from suppgram.interfaces import (
    Storage,
    Application as ApplicationInterface,
    PermissionChecker,
    Decision,
    Permission,
    WorkplaceManager,
)
from suppgram.observer import Observable
from suppgram.texts.en import EnglishTexts
from suppgram.texts.interface import Texts


class Application(ApplicationInterface):
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

        self.on_new_conversation = Observable[NewConversationEvent]()
        self.on_new_message_for_user = Observable[NewMessageForUserEvent]()
        self.on_new_unassigned_message_from_user = Observable[
            NewUnassignedMessageFromUserEvent
        ]()
        self.on_new_message_for_agent = Observable[NewMessageForAgentEvent]()

    async def create_agent(self, identification: AgentIdentification) -> Agent:
        return await self._storage.create_agent(identification)

    async def identify_agent(self, identification: AgentIdentification) -> Agent:
        return await self._storage.get_agent(identification)

    async def update_agent(self, diff: AgentDiff):
        return await self._storage.update_agent(diff)

    async def identify_user_conversation(
        self, identification: UserIdentification
    ) -> Conversation:
        user = await self._storage.get_or_create_user(identification)
        conversation = await self._storage.get_or_start_conversation(user)
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

    async def process_message_from_user(
        self, conversation: Conversation, message: Message
    ):
        await self._storage.save_message(conversation, message)
        conversation.messages.append(message)
        if len(conversation.messages) == 1:
            await self.on_new_conversation.trigger(NewConversationEvent(conversation))
        if conversation.assigned_agent and conversation.assigned_workplace:
            await self.on_new_message_for_agent.trigger(
                NewMessageForAgentEvent(
                    agent=conversation.assigned_agent,
                    workplace=conversation.assigned_workplace,
                    message=message,
                )
            )
        else:
            await self.on_new_unassigned_message_from_user.trigger(
                NewUnassignedMessageFromUserEvent(
                    message=message, conversation=conversation
                )
            )

    async def process_message_from_agent(
        self, conversation: Conversation, message: Message
    ):
        await self._storage.save_message(conversation, message)
        await self.on_new_message_for_user.trigger(
            NewMessageForUserEvent(user=conversation.user, message=message)
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
        await self._storage.assign_workplace(conversation_id, workplace)
        conversation = await self._storage.get_agent_conversation(workplace)
        await self.on_new_message_for_agent.trigger_batch(
            [
                NewMessageForAgentEvent(
                    agent=assignee, workplace=workplace, message=message
                )
                for message in conversation.messages
            ]
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
