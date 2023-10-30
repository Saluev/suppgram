import abc
from enum import Enum
from typing import List, Tuple, Any

from suppgram.entities import (
    UserIdentification,
    User,
    Agent,
    WorkplaceIdentification,
    Workplace,
    Message,
    Conversation,
    NewConversationEvent,
    NewMessageForUserEvent,
    NewMessageForAgentEvent,
)
from suppgram.observer import Observable


class PersistentStorage(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    async def get_or_create_user(self, identification: UserIdentification) -> User:
        pass

    @abc.abstractmethod
    async def get_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        pass

    @abc.abstractmethod
    async def create_agent_and_workplace(
        self, identification: WorkplaceIdentification
    ) -> Tuple[Agent, Workplace]:
        pass

    @abc.abstractmethod
    async def get_or_start_conversation(
        self, user: User, starting_state_id: str, closed_state_ids: List[str]
    ) -> Conversation:
        pass

    @abc.abstractmethod
    async def get_agent_conversation(
        self, identification: WorkplaceIdentification
    ) -> Conversation:
        pass

    @abc.abstractmethod
    async def save_message(self, conversation: Conversation, message: Message):
        pass


class Permission(str, Enum):
    pass


class Decision(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNDECIDED = "undecided"


class PermissionChecker(abc.ABC):
    @abc.abstractmethod
    def can_create_agent(self, identification: WorkplaceIdentification) -> Decision:
        pass

    @abc.abstractmethod
    def check_permission(self, agent: Agent, permission: Permission) -> Decision:
        pass


class Application(abc.ABC):
    on_new_conversation: Observable[NewConversationEvent]
    on_new_message_for_user: Observable[NewMessageForUserEvent]
    on_new_message_for_agent: Observable[NewMessageForAgentEvent]

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


class UserFrontend(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    async def start(self):
        pass


class AgentFrontend(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    async def start(self):
        pass


class ManagerFrontend(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    async def start(self):
        pass
