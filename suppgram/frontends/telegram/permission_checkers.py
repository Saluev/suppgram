from suppgram.entities import Agent, WorkplaceIdentification
from suppgram.interfaces import PermissionChecker, Permission, Decision


class TelegramOwnerIDPermissionChecker(PermissionChecker):
    def __init__(self, owner_telegram_user_id: int):
        self._owner_telegram_user_id = owner_telegram_user_id

    def can_create_agent(self, identification: WorkplaceIdentification) -> Decision:
        if identification.telegram_user_id == self._owner_telegram_user_id:
            return Decision.ALLOWED
        return Decision.UNDECIDED

    def check_permission(self, agent: Agent, permission: Permission) -> Decision:
        if agent.telegram_user_id == self._owner_telegram_user_id:
            return Decision.ALLOWED
        return Decision.UNDECIDED
