import abc
from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Any, Optional, List


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
    group: TelegramGroup
    telegram_message_id: int
    kind: TelegramMessageKind
    conversation_id: Optional[Any]


class TelegramStorage(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    async def upsert_group(self, telegram_chat_id: int):
        pass

    @abc.abstractmethod
    async def add_group_role(self, telegram_chat_id: int, role: TelegramGroupRole):
        pass

    @abc.abstractmethod
    async def get_groups_by_role(self, role: TelegramGroupRole) -> List[TelegramGroup]:
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

    @abc.abstractmethod
    async def get_messages(
        self, kind: TelegramMessageKind, conversation_id: Optional[Any] = None
    ) -> List[TelegramMessage]:
        pass
