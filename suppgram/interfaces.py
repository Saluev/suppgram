import abc
from enum import Enum
from typing import List

from suppgram.entities import (
    Agent,
    WorkplaceIdentification,
    Workplace,
)


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
