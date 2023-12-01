import abc
from enum import Enum

from suppgram.entities import WorkplaceIdentification, Agent


class Permission(str, Enum):
    MANAGE = "manage"
    SUPPORT = "support"
    TELEGRAM_ADD_GROUP_ROLE = "telegram_add_group_role"
    ASSIGN_TO_SELF = "assign_to_self"
    ASSIGN_TO_OTHERS = "assign_to_others"
    CREATE_TAGS = "create_tags"


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
