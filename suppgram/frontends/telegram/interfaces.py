import abc
from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Any, Optional, List


class TelegramGroupRole(int, Enum):
    # Group for notifications on new unassigned conversations.
    NEW_CONVERSATION_NOTIFICATIONS = 1
    # Group all members of which are agents.
    AGENTS = 2


@dataclass
class TelegramGroup:
    telegram_chat_id: int
    # telegram_chat_title: Optional[str]  # TODO
    roles: FrozenSet[TelegramGroupRole]


class TelegramMessageKind(str, Enum):
    NEW_CONVERSATION_NOTIFICATION = "new_conversation_notification"
    RATE_CONVERSATION = "rate_conversation"
    NUDGE_TO_START_BOT_NOTIFICATION = "nudge_to_start_bot"


@dataclass
class TelegramMessage:
    id: Any

    group: TelegramGroup
    telegram_message_id: int
    kind: TelegramMessageKind

    # Here be all possible parameters of all kinds of messages:
    conversation_id: Optional[Any]
    telegram_bot_username: Optional[str]


class TelegramStorage(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    async def get_group(self, telegram_chat_id: int) -> TelegramGroup:
        pass

    @abc.abstractmethod
    async def upsert_group(self, telegram_chat_id: int) -> TelegramGroup:
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
        telegram_bot_username: Optional[str] = None,
    ) -> TelegramMessage:
        pass

    @abc.abstractmethod
    async def get_messages(
        self,
        kind: TelegramMessageKind,
        conversation_id: Optional[Any] = None,
        telegram_bot_username: Optional[str] = None,
    ) -> List[TelegramMessage]:
        pass

    @abc.abstractmethod
    async def delete_messages(self, messages: List[TelegramMessage]):
        pass

    @abc.abstractmethod
    async def get_newer_messages_of_kind(
        self, messages: List[TelegramMessage]
    ) -> List[TelegramMessage]:
        pass
