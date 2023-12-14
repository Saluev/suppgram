import abc
from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Any, Optional, List

from suppgram.entities import CustomerIdentification


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
    CUSTOMER_MESSAGE_HISTORY = "customer_message_history"


@dataclass
class TelegramMessage:
    id: Any

    telegram_bot_id: int
    group: TelegramGroup
    telegram_message_id: int
    kind: TelegramMessageKind

    # Here be all possible parameters of all kinds of messages:
    customer_id: Optional[Any]
    conversation_id: Optional[Any]
    telegram_bot_username: Optional[str]

    @property
    def customer_identification(self) -> CustomerIdentification:
        if self.customer_id is None:
            raise ValueError(
                f"no customer ID in message {self.telegram_message_id} in group {self.group.telegram_chat_id}"
            )
        return CustomerIdentification(id=self.customer_id)


class TelegramStorage(abc.ABC):
    """Persistent storage for data specific to Telegram frontend.

    Currently, two entities are stored: Telegram groups and messages within groups.
    We need these data to track group roles and edit messages sent by bots if needed."""

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def get_group(self, telegram_chat_id: int) -> TelegramGroup:
        """Fetch Telegram group by Telegram chat ID."""

    @abc.abstractmethod
    async def create_or_update_group(self, telegram_chat_id: int) -> TelegramGroup:
        """Create or update Telegram group by Telegram chat ID."""

    @abc.abstractmethod
    async def add_group_roles(self, telegram_chat_id: int, *roles: TelegramGroupRole):
        """Assign roles to a Telegram group."""

    @abc.abstractmethod
    async def get_groups_by_role(self, role: TelegramGroupRole) -> List[TelegramGroup]:
        """Fetch all Telegram groups which have been assigned a role."""

    @abc.abstractmethod
    async def insert_message(
        self,
        telegram_bot_id: int,
        group: TelegramGroup,
        telegram_message_id: int,
        kind: TelegramMessageKind,
        agent_id: Optional[Any] = None,
        customer_id: Optional[Any] = None,
        conversation_id: Optional[Any] = None,
        telegram_bot_username: Optional[str] = None,
    ) -> TelegramMessage:
        """Store information about a Telegram message."""

    @abc.abstractmethod
    async def get_message(self, group: TelegramGroup, telegram_message_id: int) -> TelegramMessage:
        """Fetch a Telegram message."""

    @abc.abstractmethod
    async def get_messages(
        self,
        kind: TelegramMessageKind,
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
