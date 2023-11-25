import abc
from enum import Enum

from suppgram.entities import WorkplaceIdentification, Agent


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
