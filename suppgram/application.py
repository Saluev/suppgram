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
)
from suppgram.interfaces import (
    PersistentStorage,
    Application as ApplicationInterface,
    PermissionChecker,
    Decision,
    Permission,
)
from suppgram.observer import Observable
from suppgram.texts.en import EnglishTexts
from suppgram.texts.interface import Texts


class Application(ApplicationInterface):
    def __init__(
        self,
        storage: PersistentStorage,
        permission_checkers: List[PermissionChecker],
        texts: Texts = EnglishTexts(),
    ):
        self._storage = storage
        self._permission_checkers = permission_checkers
        self._texts = texts

        self.on_new_conversation = Observable[NewConversationEvent]()
        self.on_new_message_for_user = Observable[NewMessageForUserEvent]()
        self.on_new_message_for_agent = Observable[NewMessageForAgentEvent]()

    async def create_agent(self, identification: AgentIdentification):
        await self._storage.create_agent(identification)

    async def identify_agent(self, identification: AgentIdentification):
        return await self._storage.get_agent(identification)

    async def identify_user_conversation(
        self, identification: UserIdentification
    ) -> Conversation:
        user = await self._storage.get_or_create_user(identification)
        conversation = await self._storage.get_or_start_conversation(
            user, "foo", ["closed"]
        )
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
        if not conversation.messages:
            await self.on_new_conversation.trigger(NewConversationEvent(conversation))
        if conversation.assigned_agent and conversation.assigned_workplace:
            await self.on_new_message_for_agent.trigger(
                NewMessageForAgentEvent(
                    agent=conversation.assigned_agent,
                    workplace=conversation.assigned_workplace,
                    message=message,
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
        raise NotImplementedError
