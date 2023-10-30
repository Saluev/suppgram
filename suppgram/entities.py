from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, List


@dataclass(frozen=True)
class UserIdentification:
    telegram_user_id: Optional[int]


@dataclass(frozen=True)
class User(UserIdentification):
    id: Any


@dataclass(frozen=True)
class Agent:
    id: Any
    telegram_user_id: Optional[int]


@dataclass(frozen=True)
class WorkplaceIdentification:
    telegram_user_id: Optional[int]
    telegram_bot_id: Optional[int]
    telegram_chat_id: Optional[int]


@dataclass(frozen=True)
class Workplace(WorkplaceIdentification):
    agent: Agent


class MessageFrom(str, Enum):
    USER = "user"
    AGENT = "agent"


@dataclass(frozen=True)
class Message:
    from_: MessageFrom
    text: Optional[str]


@dataclass(frozen=True)
class Conversation:
    id: Any
    state_id: str
    user: User
    assigned_agent: Optional[Agent] = None
    assigned_workplace: Optional[Workplace] = None
    messages: List[Message] = field(default_factory=list)


@dataclass(frozen=True)
class NewConversationEvent:
    conversation: Conversation


@dataclass(frozen=True)
class NewMessageForUserEvent:
    user: User
    message: Message


@dataclass(frozen=True)
class NewMessageForAgentEvent:
    agent: Agent
    workplace: Workplace
    message: Message
