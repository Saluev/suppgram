from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any, List
from uuid import UUID


class _SetNone:
    pass


SetNone = _SetNone()


@dataclass(frozen=True)
class CustomerIdentification:
    id: Optional[Any] = None
    telegram_user_id: Optional[int] = None
    shell_uuid: Optional[UUID] = None
    pubnub_user_id: Optional[str] = None
    pubnub_channel_id: Optional[str] = None


@dataclass(frozen=True)
class Customer:
    id: Any

    telegram_user_id: Optional[int] = None
    telegram_first_name: Optional[str] = None
    telegram_last_name: Optional[str] = None
    telegram_username: Optional[str] = None

    shell_uuid: Optional[UUID] = None
    pubnub_user_id: Optional[str] = None
    pubnub_channel_id: Optional[str] = None

    @property
    def identification(self) -> CustomerIdentification:
        return CustomerIdentification(id=self.id)


@dataclass(frozen=True)
class CustomerDiff:
    telegram_first_name: Optional[str] = None
    telegram_last_name: Optional[str] = None
    telegram_username: Optional[str] = None


@dataclass(frozen=True)
class AgentIdentification:
    id: Optional[Any] = None
    telegram_user_id: Optional[int] = None


@dataclass(frozen=True)
class Agent:
    id: Any

    telegram_user_id: Optional[int] = None
    telegram_first_name: Optional[str] = None
    telegram_last_name: Optional[str] = None
    telegram_username: Optional[str] = None

    @property
    def identification(self) -> AgentIdentification:
        return AgentIdentification(id=self.id)


@dataclass(frozen=True)
class AgentDiff:
    telegram_first_name: Optional[str] = None
    telegram_last_name: Optional[str] = None
    telegram_username: Optional[str] = None


@dataclass(frozen=True)
class WorkplaceIdentification:
    telegram_user_id: Optional[int]
    telegram_bot_id: Optional[int]

    def to_agent_identification(self) -> AgentIdentification:
        return AgentIdentification(telegram_user_id=self.telegram_user_id)


@dataclass(frozen=True)
class Workplace(WorkplaceIdentification):
    """
    Workplace is an abstraction over a way agent conveys their messages.
    Examples of workplace include:
      - private Telegram chat with one of the agent bots, identified by user ID and bot ID
      - PubNub chat, identified by chat ID
      - web interface session, identified by active websocket identifier
    """

    id: Any
    agent: Agent


class MessageKind(str, Enum):
    FROM_CUSTOMER = "from_customer"
    FROM_AGENT = "from_agent"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class Message:
    kind: MessageKind
    time_utc: datetime
    text: Optional[str] = None


class ConversationState(str, Enum):
    NEW = "new"
    ASSIGNED = "assigned"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class ConversationTag:
    id: Any
    name: str
    created_at_utc: datetime
    created_by: Agent


@dataclass(frozen=True)
class Conversation:
    id: Any
    state: str
    customer: Customer
    tags: List[ConversationTag]
    assigned_agent: Optional[Agent] = None
    assigned_workplace: Optional[Workplace] = None
    messages: List[Message] = field(default_factory=list)
    customer_rating: Optional[int] = None


@dataclass(frozen=True)
class ConversationDiff:
    state: Optional[str] = None
    assigned_workplace_id: Optional[Any] | _SetNone = None
    added_tags: Optional[List[ConversationTag]] = None
    removed_tags: Optional[List[ConversationTag]] = None
    customer_rating: Optional[int] = None


@dataclass(frozen=True)
class ConversationEvent:
    conversation: Conversation


@dataclass(frozen=True)
class ConversationTagEvent:
    conversation: Conversation
    tag: ConversationTag


@dataclass(frozen=True)
class NewMessageForCustomerEvent:
    customer: Customer
    conversation: Conversation
    message: Message


@dataclass(frozen=True)
class NewUnassignedMessageFromCustomerEvent:
    message: Message
    conversation: Conversation


@dataclass(frozen=True)
class NewMessageForAgentEvent:
    agent: Agent
    workplace: Workplace
    message: Message
