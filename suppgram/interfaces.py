import abc
from enum import Enum
from typing import List, Any

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
    AgentIdentification,
    NewUnassignedMessageFromUserEvent,
    AgentDiff,
)
from suppgram.observer import Observable


class Storage(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    async def get_or_create_user(self, identification: UserIdentification) -> User:
        pass

    @abc.abstractmethod
    async def get_agent(self, identification: AgentIdentification) -> Agent:
        pass

    @abc.abstractmethod
    async def create_agent(self, identification: AgentIdentification) -> Agent:
        pass

    @abc.abstractmethod
    async def update_agent(self, diff: AgentDiff):
        pass

    @abc.abstractmethod
    async def get_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        pass

    @abc.abstractmethod
    async def get_agent_workplaces(self, agent: Agent) -> List[Workplace]:
        pass

    @abc.abstractmethod
    async def get_or_create_workplace(
        self, agent: Agent, identification: WorkplaceIdentification
    ) -> Workplace:
        pass

    @abc.abstractmethod
    async def get_or_start_conversation(self, user: User) -> Conversation:
        pass

    @abc.abstractmethod
    async def assign_workplace(self, conversation_id: Any, workplace: Workplace):
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
    MANAGE = "manage"
    SUPPORT = "support"
    TELEGRAM_GROUP_ROLE_ADD = "telegram_group_role_add"
    ASSIGN_TO_SELF = "assign_to_self"
    ASSIGN_TO_OTHERS = "assign_to_others"


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
    on_new_unassigned_message_from_user = Observable[NewUnassignedMessageFromUserEvent]
    on_new_message_for_agent: Observable[NewMessageForAgentEvent]

    @abc.abstractmethod
    async def create_agent(self, identification: AgentIdentification) -> Agent:
        pass

    @abc.abstractmethod
    async def identify_agent(self, identification: AgentIdentification) -> Agent:
        pass

    @abc.abstractmethod
    async def update_agent(self, diff: AgentDiff):
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


class WorkplaceManager(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    def create_missing_workplaces(
        self, agent: Agent, existing_workplaces: List[Workplace]
    ) -> List[WorkplaceIdentification]:
        pass

    def filter_available_workplaces(
        self, workplaces: List[Workplace]
    ) -> List[Workplace]:
        return workplaces


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
