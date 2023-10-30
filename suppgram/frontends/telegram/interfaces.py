import abc
from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Any, Optional


class TelegramGroupRole(int, Enum):
    # Group for notifications on new unassigned conversations.
    NEW_CONVERSATION_NOTIFICATIONS = 1


@dataclass
class TelegramGroup:
    telegram_chat_id: int
    roles: FrozenSet[TelegramGroupRole]


class TelegramMessageKind(str, Enum):
    NEW_CONVERSATION_NOTIFICATION = "new_conversation_notification"


@dataclass
class TelegramMessage:
    telegram_group: TelegramGroup
    telegram_message_id: int
    kind: TelegramMessageKind
    conversation_id: Optional[Any]


class TelegramStorage(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    async def get_group_by_role(self, role: TelegramGroupRole) -> TelegramGroup:
        pass

    @abc.abstractmethod
    async def insert_message(
        self,
        group: TelegramGroup,
        telegram_message_id: int,
        kind: TelegramMessageKind,
        conversation_id: Optional[Any] = None,
    ):
        pass
