from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, List, Union
from uuid import UUID


class _SetNone:
    pass


SetNone = _SetNone()


@dataclass(frozen=True)
class CustomerIdentification:
    """Subset of [Customer][suppgram.entities.Customer] fields allowing to uniquely identify the customer."""

    id: Optional[Any] = None
    telegram_user_id: Optional[int] = None
    shell_uuid: Optional[UUID] = None
    pubnub_user_id: Optional[str] = None
    pubnub_channel_id: Optional[str] = None


@dataclass(frozen=True)
class Customer:
    """
    Describes a particular customer who is interacting with the support system.

    Contains the data necessary to identify the external system customer communicates
    through (e. g. Telegram bot, Instagram business account, PubNub chat, etc.),
    the data necessary to identify the customer and send them messages within that system,
    and all available metadata (e.g. first name, last name) that can be useful.

    Attributes:
        id: internal ID of the customer. Type and format may depend on chosen [storage][suppgram.storage.Storage].
        telegram_user_id: Telegram user ID, if the customer is communicating via a Telegram bot.
        telegram_first_name: Telegram user first name, if the customer is communicating via a Telegram bot
                             and has non-empty first name.
        telegram_last_name: Telegram user last name, if the customer is communicating via a Telegram bot
                            and has non-empty last name.
        telegram_username: Telegram user username, if the customer is communicating via a Telegram bot
                           and their Telegram privacy settings allow access to their username.
        shell_uuid: UUID of the customer, if the customer is communicating via shell interface.
        pubnub_user_id: PubNub user ID, if the customer is communicating via a PubNub channel.
        pubnub_channel_id: PubNub channel ID, if the customer is communicating via a PubNub channel.
    """

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
    """Describes an update to a [Customer][suppgram.entities.Customer] object.

    Is, in fact, a subset of [Customer][suppgram.entities.Customer] fields representing optional metadata.
    """

    telegram_first_name: Optional[str] = None
    telegram_last_name: Optional[str] = None
    telegram_username: Optional[str] = None


@dataclass(frozen=True)
class AgentIdentification:
    """Subset of [Agent][suppgram.entities.Agent] fields allowing to uniquely identify the agent."""

    id: Optional[Any] = None
    telegram_user_id: Optional[int] = None


@dataclass(frozen=True)
class Agent:
    """
    Describes support agent who is able to communicate with customers via the support system or manage other agents.

    Attributes:
        id: internal ID of the agent. Type and format may depend on chosen [storage][suppgram.storage.Storage].
        telegram_user_id: Telegram user ID, if the agent is working via Telegram interface.
        telegram_first_name: Telegram user first name, if the agent is working via Telegram interface
                             and has non-empty first name.
        telegram_last_name: Telegram user last name, if the agent is working via Telegram interface
                            and has non-empty last name.
        telegram_username: Telegram user username, if the agent is working via Telegram interface
                           and their Telegram privacy settings allow access to their username.
    """

    id: Any
    deactivated: bool

    telegram_user_id: Optional[int] = None
    telegram_first_name: Optional[str] = None
    telegram_last_name: Optional[str] = None
    telegram_username: Optional[str] = None

    @property
    def identification(self) -> AgentIdentification:
        return AgentIdentification(id=self.id)


@dataclass(frozen=True)
class AgentDiff:
    """Describes an update to a [Agent][suppgram.entities.Agent] object.

    Is, in fact, a subset of [Agent][suppgram.entities.Agent] fields representing optional metadata.
    """

    deactivated: Optional[bool] = None

    telegram_first_name: Optional[str] = None
    telegram_last_name: Optional[str] = None
    telegram_username: Optional[str] = None


@dataclass(frozen=True)
class WorkplaceIdentification:
    """Subset of [Workplace][suppgram.entities.Workplace] fields allowing to uniquely identify the workplace."""

    id: Optional[Any] = None

    telegram_user_id: Optional[int] = None
    telegram_bot_id: Optional[int] = None

    def to_agent_identification(self) -> AgentIdentification:
        if self.telegram_user_id is not None:
            return AgentIdentification(telegram_user_id=self.telegram_user_id)
        raise RuntimeError(
            ".to_agent_identification() should not be called for already existing workplaces with IDs"
        )


@dataclass(frozen=True)
class Workplace:
    """
    Describes support agent's workplace.

    Workplace is an abstraction over a way agent conveys their messages.
    Examples of a workplace include:

      * private Telegram chat with one of the agent bots, identified by user ID and bot ID;
      * PubNub chat, identified by chat ID;
      * web interface session, identified by active websocket identifier.

    Attributes:
        id: internal ID of the workplace. Type and format may depend on chosen [storage][suppgram.storage.Storage].
        agent: agent the workplace belongs to.
    """

    id: Any

    telegram_user_id: Optional[int]
    telegram_bot_id: Optional[int]

    agent: Agent

    @property
    def identification(self) -> WorkplaceIdentification:
        return WorkplaceIdentification(
            id=self.id, telegram_user_id=self.telegram_user_id, telegram_bot_id=self.telegram_bot_id
        )


class MessageKind(str, Enum):
    """Enumeration describing [message][suppgram.entities.Message] kind."""

    FROM_CUSTOMER = "from_customer"
    """ Regular message from a customer. """
    FROM_AGENT = "from_agent"
    """ Regular message from a currently assigned agent. """
    POSTPONED = "postponed"
    """ Internal message marking the moment the conversation was postponed by the agent."""
    RESOLVED = "resolved"
    """ Internal message marking the moment the conversation was resolved by the agent. """


@dataclass(frozen=True)
class Message:
    """
    Describes message within a [conversation][suppgram.entities.Conversation].

    May be a message from customer, agent, or an internal message corresponding
    to an event (e.g. conversation resolution) depending on `kind`.

    Attributes:
        kind: message kind.
        time_utc: date and time of message creation.
        text: message text, if this is a text message.
        image: image data, if this is an image message.
    """

    kind: MessageKind
    time_utc: datetime
    text: Optional[str] = None
    image: Optional[bytes] = None
    # don't forget to add new `MessageMediaKind`
    # when implementing images, videos, etc.

    @property
    def media_kind(self) -> "MessageMediaKind":
        if self.text is not None:
            return MessageMediaKind.TEXT
        if self.image is not None:
            return MessageMediaKind.IMAGE
        return MessageMediaKind.NONE


class ConversationState(str, Enum):
    """
    Enumeration describing current state of a [conversation][suppgram.entities.Conversation].

    Attributes:
        NEW: newly created conversation waiting for an agent to be assigned
        ASSIGNED: in-progress conversation with an assigned agent
        RESOLVED: conversation resolved by an agent
    """

    NEW = "new"
    ASSIGNED = "assigned"
    RESOLVED = "resolved"


FINAL_STATES = [ConversationState.RESOLVED]
""" List of states in which the conversation is not considered
 ready to accept new messages from the customer. """


@dataclass(frozen=True)
class Tag:
    """
    Describes tag that can be used to label a [conversation][suppgram.entities.Conversation].

    Attributes:
        id: internal ID of the tag. Type and format may depend on chosen [storage][suppgram.storage.Storage].
        name: tag name.
        created_at_utc: date and time when the tag was created.
        created_by: agent who has created the tag.
    """

    id: Any
    name: str
    created_at_utc: datetime
    created_by: Agent


@dataclass(frozen=True)
class Conversation:
    """
    Describes a particular conversation between customer and support agent(s).

    When a [customer][suppgram.entities.Customer] sends a message into the support system,
    a new conversation is created. It can then be assigned to an [agent][suppgram.entities.Agent]
    and resolved by them. If the customer sends a message again, previously resolved conversations
    are ignored and a new one is spawned.

    Attributes:
        id: internal ID of the conversation. Type and format may depend on chosen [storage][suppgram.storage.Storage].
        state: current state of the conversation.
        customer: customer who has started the conversation.
        tags: list of tags added to the conversation.
        assigned_agent: agent currently assigned to the conversation.
        assigned_workplace: workplace currently assigned to the conversation.
        messages: list of [messages][suppgram.entities.Message] from the beginning of the conversation.
                  Includes customer's messages, agent's messages, and internal messages marking particular
                  events (e.g. conversation resolution).
        customer_rating: 5-star rating given by the customer after the resolution of the conversation.
    """

    id: Any
    state: ConversationState
    customer: Customer
    tags: List[Tag]
    assigned_agent: Optional[Agent] = None
    assigned_workplace: Optional[Workplace] = None
    messages: List[Message] = field(default_factory=list)
    customer_rating: Optional[int] = None


@dataclass(frozen=True)
class ConversationDiff:
    """
    Describes an update to a [Conversation][suppgram.entities.Conversation] object.

    Attributes:
        state: new state of the conversation.
        assigned_workplace_id: ID of the [workplace][suppgram.entities.Workplace] newly assigned to the
                               conversation. Note that workplaces have many-to-one relationship with
                               [agents][suppgram.entities.Agent], thus agent ID is not necessary here.
        added_tags: list of tags to add to the conversation.
        removed_tags: list of tags to remove from the conversation.
        customer_rating: 5-star rating newly given by a customer.
    """

    state: Optional[ConversationState] = None
    assigned_workplace_id: Union[Optional[Any], _SetNone] = None
    added_tags: Optional[List[Tag]] = None
    removed_tags: Optional[List[Tag]] = None
    customer_rating: Optional[int] = None

    @property
    def assigned_workplace_identification(self) -> Optional[WorkplaceIdentification]:
        if self.assigned_workplace_id in (None, SetNone):
            return None
        return WorkplaceIdentification(id=self.assigned_workplace_id)


# Data classes for analytics


class EventKind(str, Enum):
    AGENT_ASSIGNED = "agent_assigned"
    CONVERSATION_POSTPONED = "conversation_postponed"
    CONVERSATION_RATED = "conversation_rated"
    CONVERSATION_RESOLVED = "conversation_resolved"
    CONVERSATION_STARTED = "conversation_started"
    CONVERSATION_TAG_ADDED = "conversation_tag_added"
    CONVERSATION_TAG_REMOVED = "conversation_tag_removed"
    MESSAGE_SENT = "message_sent"


class MessageMediaKind(str, Enum):
    NONE = "none"
    TEXT = "text"
    IMAGE = "image"
    # images, videos, etc.


@dataclass(frozen=True)
class Event:
    """Describes arbitrary event within Suppgram application, with all relevant entities linked by their IDs."""

    kind: EventKind
    time_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    agent_id: Optional[Any] = None
    conversation_id: Optional[Any] = None
    customer_id: Optional[Any] = None
    message_kind: Optional[MessageKind] = None
    message_media_kind: Optional[MessageMediaKind] = None
    tag_id: Optional[Any] = None
    workplace_id: Optional[Any] = None


# Data classes for observables


@dataclass(frozen=True)
class ConversationEvent:
    conversation: Conversation


@dataclass(frozen=True)
class ConversationTagEvent:
    conversation: Conversation
    tag: Tag


@dataclass(frozen=True)
class NewMessageForCustomerEvent:
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


@dataclass(frozen=True)
class TagEvent:
    tag: Tag
