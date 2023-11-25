from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any, List


class _SetNone:
    pass


SetNone = _SetNone()


@dataclass(frozen=True)
class UserIdentification:
    telegram_user_id: Optional[int]


@dataclass(frozen=True)
class User(UserIdentification):
    id: Any


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
    FROM_USER = "user"
    FROM_AGENT = "agent"


@dataclass(frozen=True)
class Message:
    kind: MessageKind
    time_utc: datetime
    text: Optional[str]


class ConversationState(str, Enum):
    NEW = "new"
    ASSIGNED = "assigned"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class Conversation:
    id: Any
    state: str
    user: User
    assigned_agent: Optional[Agent] = None
    assigned_workplace: Optional[Workplace] = None
    messages: List[Message] = field(default_factory=list)


@dataclass(frozen=True)
class ConversationDiff:
    state: Optional[str] = None
    assigned_workplace: Optional[Workplace] | SetNone = None


@dataclass(frozen=True)
class ConversationEvent:
    conversation: Conversation


@dataclass(frozen=True)
class NewMessageForUserEvent:
    user: User
    message: Message


@dataclass(frozen=True)
class NewUnassignedMessageFromUserEvent:
    message: Message
    conversation: Conversation


@dataclass(frozen=True)
class NewMessageForAgentEvent:
    agent: Agent
    workplace: Workplace
    message: Message
