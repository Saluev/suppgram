import abc
from typing import Any

from suppgram.entities import (
    ConversationEvent,
    NewMessageForUserEvent,
    NewUnassignedMessageFromUserEvent,
    NewMessageForAgentEvent,
    AgentIdentification,
    Agent,
    AgentDiff,
    UserIdentification,
    Conversation,
    WorkplaceIdentification,
    Workplace,
    Message,
)
from suppgram.interfaces import Permission
from suppgram.observer import Observable


class Backend(abc.ABC):
    on_new_conversation: Observable[ConversationEvent]
    on_conversation_assignment: Observable[ConversationEvent]
    on_conversation_resolution: Observable[ConversationEvent]
    on_new_message_for_user: Observable[NewMessageForUserEvent]
    on_new_unassigned_message_from_user = Observable[NewUnassignedMessageFromUserEvent]
    on_new_message_for_agent: Observable[NewMessageForAgentEvent]

    @abc.abstractmethod
    async def create_agent(self, identification: AgentIdentification) -> Agent:
        pass

    @abc.abstractmethod
    async def identify_agent(self, identification: AgentIdentification) -> Agent:
        pass

    @abc.abstractmethod
    async def update_agent(self, identification: AgentIdentification, diff: AgentDiff):
        pass

    @abc.abstractmethod
    async def identify_user_conversation(
        self, identification: UserIdentification
    ) -> Conversation:
        pass

    @abc.abstractmethod
    async def identify_workplace(
        self, identification: WorkplaceIdentification
    ) -> Workplace:
        pass

    @abc.abstractmethod
    def check_permission(self, agent: Agent, permission: Permission) -> bool:
        pass

    @abc.abstractmethod
    async def identify_agent_conversation(
        self, identification: WorkplaceIdentification
    ) -> Conversation:
        pass

    @abc.abstractmethod
    async def process_message_from_user(
        self, conversation: Conversation, message: Message
    ):
        pass

    @abc.abstractmethod
    async def process_message_from_agent(
        self, conversation: Conversation, message: Message
    ):
        pass

    @abc.abstractmethod
    async def assign_agent(
        self, assigner: Agent, assignee: Agent, conversation_id: Any
    ):
        pass

    @abc.abstractmethod
    async def resolve_conversation(self, resolver: Agent, conversation: Conversation):
        pass
