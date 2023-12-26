import abc
from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Any, Optional, List

from suppgram.entities import CustomerIdentification


class TelegramChatRole(int, Enum):
    # Group for notifications on new unassigned conversations.
    NEW_CONVERSATION_NOTIFICATIONS = 1
    # Group all members of which are agents.
    AGENTS = 2


@dataclass(frozen=True)
class TelegramChat:
    telegram_chat_id: int
    roles: FrozenSet[TelegramChatRole]


class TelegramMessageKind(str, Enum):
    NEW_CONVERSATION_NOTIFICATION = "new_conversation_notification"
    RATE_CONVERSATION = "rate_conversation"
    NUDGE_TO_START_BOT_NOTIFICATION = "nudge_to_start_bot"
    CUSTOMER_MESSAGE_HISTORY = "customer_message_history"


@dataclass(frozen=True)
class TelegramMessage:
    id: Any

    telegram_bot_id: int
    chat: TelegramChat
    telegram_message_id: int
    kind: TelegramMessageKind

    # Here be all possible parameters of all kinds of messages:
    agent_id: Optional[Any]
    customer_id: Optional[Any]
    conversation_id: Optional[Any]
    telegram_bot_username: Optional[str]

    @property
    def customer_identification(self) -> CustomerIdentification:
        if self.customer_id is None:
            raise ValueError(
                f"no customer ID in message {self.telegram_message_id} in group {self.chat.telegram_chat_id}"
            )
        return CustomerIdentification(id=self.customer_id)


class TelegramStorage(abc.ABC):
    """Persistent storage for data specific to Telegram frontend.

    Currently, two entities are stored: Telegram chats and messages within chats.
    We need these data to track group roles and edit messages sent by bots if needed."""

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def get_chat(self, telegram_chat_id: int) -> TelegramChat:
        """Fetch Telegram chat by Telegram chat ID."""

    @abc.abstractmethod
    async def create_or_update_chat(self, telegram_chat_id: int) -> TelegramChat:
        """Create or update Telegram chat by Telegram chat ID."""

    @abc.abstractmethod
    async def add_chat_roles(self, telegram_chat_id: int, *roles: TelegramChatRole) -> object:
        """Assign roles to a Telegram chat."""

    @abc.abstractmethod
    async def get_chats_by_role(self, role: TelegramChatRole) -> List[TelegramChat]:
        """Fetch all Telegram chats which have been assigned a role."""

    @abc.abstractmethod
    async def insert_message(
        self,
        telegram_bot_id: int,
        chat: TelegramChat,
        telegram_message_id: int,
        kind: TelegramMessageKind,
        *,
        agent_id: Optional[Any] = None,
        customer_id: Optional[Any] = None,
        conversation_id: Optional[Any] = None,
        telegram_bot_username: Optional[str] = None,
    ) -> TelegramMessage:
        """Store information about a Telegram message."""

    @abc.abstractmethod
    async def get_message(self, chat: TelegramChat, telegram_message_id: int) -> TelegramMessage:
        """Fetch a Telegram message."""

    @abc.abstractmethod
    async def get_messages(
        self,
        kind: TelegramMessageKind,
        *,
        agent_id: Optional[Any] = None,
        conversation_id: Optional[Any] = None,
        telegram_bot_username: Optional[str] = None,
    ) -> List[TelegramMessage]:
        """Fetch all Telegram messages satisfying condition(s)."""

    @abc.abstractmethod
    async def delete_messages(self, messages: List[TelegramMessage]):
        """Delete given Telegram messages."""

    @abc.abstractmethod
    async def get_newer_messages_of_kind(
        self, messages: List[TelegramMessage]
    ) -> List[TelegramMessage]:
        """For all given messages, find all newer messages in the corresponding chats.

        "Newer" here means "with greater Telegram message ID"."""
