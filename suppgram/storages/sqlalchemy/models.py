from datetime import datetime, timezone
from typing import List, Any, Optional, Mapping, Dict
from uuid import UUID

from sqlalchemy import (
    Integer,
    String,
    ForeignKey,
    DateTime,
    Table,
    Column,
    Enum,
    ColumnElement,
    Boolean, LargeBinary,
)
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import (
    declarative_base,
    Mapped,
    mapped_column,
    relationship,
    joinedload,
    selectinload,
)
from sqlalchemy.orm.interfaces import LoaderOption

from suppgram.containers import UnavailableList
from suppgram.entities import (
    Agent as AgentInterface,
    AgentDiff,
    AgentIdentification,
    Conversation as ConversationInterface,
    ConversationDiff,
    ConversationState,
    Customer as CustomerInterface,
    CustomerDiff,
    CustomerIdentification,
    Event as EventInterface,
    EventKind,
    FINAL_STATES,
    Message as ConversaionMessageInterface,
    MessageKind,
    MessageMediaKind,
    SetNone,
    Tag as TagInterface,
    Workplace as WorkplaceInterface,
    WorkplaceIdentification,
)
from suppgram.errors import AgentEmptyIdentification, WorkplaceEmptyIdentification

Base = declarative_base()


class Customer(Base):
    __tablename__ = "suppgram_customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, nullable=True, unique=True)
    telegram_first_name: Mapped[str] = mapped_column(String, nullable=True)
    telegram_last_name: Mapped[str] = mapped_column(String, nullable=True)
    telegram_username: Mapped[str] = mapped_column(String, nullable=True)
    shell_uuid: Mapped[str] = mapped_column(String, nullable=True, unique=True)
    pubnub_user_id: Mapped[str] = mapped_column(
        String, nullable=True
    )  # TODO unique together with channel
    pubnub_channel_id: Mapped[str] = mapped_column(String, nullable=True)
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="customer")


class Agent(Base):
    __tablename__ = "suppgram_agents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deactivated: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_user_id: Mapped[int] = mapped_column(Integer, nullable=True, unique=True)
    telegram_first_name: Mapped[str] = mapped_column(String, nullable=True)
    telegram_last_name: Mapped[str] = mapped_column(String, nullable=True)
    telegram_username: Mapped[str] = mapped_column(String, nullable=True)
    workplaces: Mapped[List["Workplace"]] = relationship(back_populates="agent")
    created_tags: Mapped[List["Tag"]] = relationship(
        back_populates="created_by"
    )  # `created_tags` is not really needed, but without it mypy terminates with an exception...


class Workplace(Base):
    __tablename__ = "suppgram_workplaces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey(Agent.id))
    agent: Mapped[Agent] = relationship(back_populates="workplaces")
    telegram_bot_id: Mapped[int] = mapped_column(Integer)
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="assigned_workplace")


class Tag(Base):
    __tablename__ = "suppgram_tags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey(Agent.id), nullable=False)
    created_by: Mapped[Agent] = relationship(back_populates="created_tags")
    # `back_populates` is not really needed, but without it mypy terminates with an exception...


association_table = Table(
    "suppgram_conversation_tag_associations",
    Base.metadata,
    Column("conversation_id", ForeignKey("suppgram_conversations.id"), primary_key=True),
    Column("tag_id", ForeignKey("suppgram_tags.id"), primary_key=True),
)


class Conversation(Base):
    __tablename__ = "suppgram_conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey(Customer.id), nullable=False)
    customer: Mapped[Customer] = relationship(back_populates="conversations")
    tags: Mapped[List[Tag]] = relationship(secondary=association_table)
    assigned_workplace_id: Mapped[int] = mapped_column(ForeignKey(Workplace.id), nullable=True)
    assigned_workplace: Mapped[Workplace] = relationship(back_populates="conversations")
    state: Mapped[ConversationState] = mapped_column(Enum(ConversationState), nullable=False)
    messages: Mapped[List["ConversationMessage"]] = relationship(back_populates="conversation")
    customer_rating: Mapped[int] = mapped_column(Integer, nullable=True)


class ConversationMessage(Base):
    __tablename__ = "suppgram_conversation_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey(Conversation.id), nullable=False)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    kind: Mapped[MessageKind] = mapped_column(Enum(MessageKind), nullable=False)
    time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=True)
    image: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)


class Event(Base):
    __tablename__ = "suppgram_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[EventKind] = mapped_column(Enum(EventKind), nullable=False)
    time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    agent_id: Mapped[int] = mapped_column(ForeignKey(Agent.id), nullable=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey(Conversation.id), nullable=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey(Customer.id), nullable=True)
    message_kind: Mapped[MessageKind] = mapped_column(Enum(MessageKind), nullable=True)
    message_media_kind: Mapped[MessageMediaKind] = mapped_column(
        Enum(MessageMediaKind), nullable=True
    )
    tag_id: Mapped[int] = mapped_column(ForeignKey(Tag.id), nullable=True)
    workplace_id: Mapped[int] = mapped_column(ForeignKey(Workplace.id), nullable=True)


class Models:
    """Abstraction layer over SQLAlchemy models.

    Default models are declared in `suppgram.storages.sqlalchemy.models` package."""

    def __init__(
        self,
        engine: AsyncEngine,
        customer_model: Any = Customer,
        agent_model: Any = Agent,
        workplace_model: Any = Workplace,
        conversation_model: Any = Conversation,
        conversation_message_model: Any = ConversationMessage,
        tag_model: Any = Tag,
        conversation_tag_association_table: Optional[Table] = association_table,
        event_model: Any = Event,
    ):
        """
        Parameters:
            engine: asynchronous SQLAlchemy engine
            customer_model: SQLAlchemy model for customers
            agent_model: SQLAlchemy model for agents
            workplace_model: SQLAlchemy model for workplaces
            conversation_model: SQLAlchemy model for conversations
            conversation_message_model: SQLAlchemy model for messages
            tag_model: SQLAlchemy model for conversation tags
            event_model: SQLAlchemy model for events
        """
        self._engine = engine
        self.customer_model = customer_model
        self.agent_model = agent_model
        self.workplace_model = workplace_model
        self.conversation_model = conversation_model
        self.conversation_message_model = conversation_message_model
        self.tag_model = tag_model
        self.event_model = event_model
        self._conversation_tag_association_table = conversation_tag_association_table

    async def initialize(self):
        tables_to_create = [
            built_in_model_or_table
            if isinstance(built_in_model_or_table, Table)
            else built_in_model_or_table.__table__
            for model_or_table, built_in_model_or_table in [
                (self.customer_model, Customer),
                (self.agent_model, Agent),
                (self.workplace_model, Workplace),
                (self.conversation_model, Conversation),
                (self.conversation_message_model, ConversationMessage),
                (self.tag_model, Tag),
                (self.event_model, Event),
                (self._conversation_tag_association_table, association_table),
            ]
            if model_or_table is built_in_model_or_table
        ]
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=tables_to_create)

    def convert_to_customer_model(self, identification: CustomerIdentification) -> Any:
        if identification.id is not None:
            raise ValueError("can't create customer with predefined ID")
        return self.customer_model(
            telegram_user_id=identification.telegram_user_id,
            shell_uuid=identification.shell_uuid.hex if identification.shell_uuid else None,
            pubnub_user_id=identification.pubnub_user_id,
            pubnub_channel_id=identification.pubnub_channel_id,
        )

    def apply_diff_to_customer_model(self, model: Customer, diff: CustomerDiff):
        if diff.telegram_first_name is not None:
            model.telegram_first_name = diff.telegram_first_name
        if diff.telegram_last_name is not None:
            model.telegram_last_name = diff.telegram_last_name
        if diff.telegram_username is not None:
            model.telegram_username = diff.telegram_username

    def convert_from_customer_model(self, customer: Customer) -> CustomerInterface:
        return CustomerInterface(
            id=customer.id,
            telegram_user_id=customer.telegram_user_id,
            telegram_first_name=customer.telegram_first_name,
            telegram_last_name=customer.telegram_last_name,
            telegram_username=customer.telegram_username,
            shell_uuid=UUID(customer.shell_uuid) if customer.shell_uuid else None,
            pubnub_user_id=customer.pubnub_user_id,
            pubnub_channel_id=customer.pubnub_channel_id,
        )

    def convert_to_agent_model(self, identification: AgentIdentification) -> Any:
        if identification.id is not None:
            raise ValueError("can't create agent with predefined ID")
        return self.agent_model(
            telegram_user_id=identification.telegram_user_id,
        )

    def apply_diff_to_agent_model(self, model: Agent, diff: AgentDiff):
        if diff.deactivated is not None:
            model.deactivated = diff.deactivated
        if diff.telegram_first_name is not None:
            model.telegram_first_name = diff.telegram_first_name
        if diff.telegram_last_name is not None:
            model.telegram_last_name = diff.telegram_last_name
        if diff.telegram_username is not None:
            model.telegram_username = diff.telegram_username

    def convert_from_agent_model(self, agent: Agent) -> AgentInterface:
        return AgentInterface(
            id=agent.id,
            deactivated=agent.deactivated,
            telegram_user_id=agent.telegram_user_id,
            telegram_first_name=agent.telegram_first_name,
            telegram_last_name=agent.telegram_last_name,
            telegram_username=agent.telegram_username,
        )

    def convert_to_workplace_model(
        self, agent_id: Any, identification: WorkplaceIdentification
    ) -> Any:
        return self.workplace_model(
            agent_id=agent_id,
            telegram_bot_id=identification.telegram_bot_id,
        )

    def convert_from_workplace_model(
        self, agent: AgentInterface, workplace: Workplace
    ) -> WorkplaceInterface:
        return WorkplaceInterface(
            id=workplace.id,
            telegram_user_id=agent.telegram_user_id,
            telegram_bot_id=workplace.telegram_bot_id,
            agent=agent,
        )

    def convert_to_message_model(
        self, conversation_id: Any, message: ConversaionMessageInterface
    ) -> Any:
        return self.conversation_message_model(
            conversation_id=conversation_id,
            kind=message.kind,
            time_utc=message.time_utc,
            text=message.text,
            image=message.image,
        )

    def convert_from_message_model(
        self, message: ConversationMessage
    ) -> ConversaionMessageInterface:
        return ConversaionMessageInterface(
            kind=message.kind, time_utc=message.time_utc, text=message.text, image=message.image
        )

    def make_tag_model(self, name: str, created_by: AgentInterface) -> Tag:
        return Tag(
            name=name,  # type: ignore
            created_at_utc=datetime.now(timezone.utc),  # type: ignore
            created_by_id=created_by.id,  # type: ignore
        )

    def convert_from_tag_model(self, tag: Tag, created_by: AgentInterface) -> TagInterface:
        return TagInterface(
            id=tag.id,
            name=tag.name,
            created_at_utc=tag.created_at_utc,
            created_by=created_by,
        )

    def convert_from_conversation_model(
        self, conversation: Conversation, with_messages: bool
    ) -> ConversationInterface:
        assigned_agent: Optional[AgentInterface] = None
        assigned_workplace: Optional[WorkplaceInterface] = None
        if conversation.assigned_workplace:
            assigned_agent = self.convert_from_agent_model(conversation.assigned_workplace.agent)
            assigned_workplace = self.convert_from_workplace_model(
                assigned_agent, conversation.assigned_workplace
            )
        return ConversationInterface(
            id=conversation.id,
            state=conversation.state,
            customer=self.convert_from_customer_model(conversation.customer),
            tags=[
                self.convert_from_tag_model(tag, self.convert_from_agent_model(tag.created_by))
                for tag in conversation.tags
            ],
            assigned_agent=assigned_agent,
            assigned_workplace=assigned_workplace,
            messages=[self.convert_from_message_model(message) for message in conversation.messages]
            if with_messages
            else UnavailableList[ConversaionMessageInterface](),
            customer_rating=conversation.customer_rating,
        )

    def make_customer_filter(self, identification: CustomerIdentification) -> ColumnElement:
        model = self.customer_model

        if identification.id is not None:
            return model.id == identification.id

        if identification.telegram_user_id is not None:
            return model.telegram_user_id == identification.telegram_user_id

        if identification.pubnub_user_id is not None:
            return (model.pubnub_user_id == identification.pubnub_user_id) & (
                model.pubnub_channel_id == identification.pubnub_channel_id
            )

        if identification.shell_uuid is not None:
            return model.shell_uuid == str(identification.shell_uuid)

        raise ValueError(
            f"received customer identification {identification} without supported non-null fields"
        )

    def make_agent_filter(self, identification: AgentIdentification) -> ColumnElement:
        model = self.agent_model

        if identification.id is not None:
            return model.id == identification.id

        if identification.telegram_user_id is not None:
            return model.telegram_user_id == identification.telegram_user_id

        raise AgentEmptyIdentification(identification)

    def make_workplace_filter(self, identification: WorkplaceIdentification) -> ColumnElement:
        workplace_model = self.workplace_model
        agent_model = self.agent_model
        if identification.id is not None:
            return (workplace_model.id == identification.id) & (
                workplace_model.agent_id == agent_model.id
            )
        if identification.telegram_user_id is not None:
            return (
                (workplace_model.telegram_bot_id == identification.telegram_bot_id)
                & (workplace_model.agent_id == agent_model.id)
                & (agent_model.telegram_user_id == identification.telegram_user_id)
            )
        raise WorkplaceEmptyIdentification(identification)

    def make_agent_workplaces_filter(self, agent: AgentInterface) -> ColumnElement:
        return self.workplace_model.agent_id == agent.id

    def make_current_customer_conversation_filter(self, customer: CustomerInterface):
        return (self.conversation_model.customer_id == customer.id) & (
            ~self.conversation_model.state.in_(FINAL_STATES)
        )

    def make_workplace_conversation_filter(
        self, identification: WorkplaceIdentification
    ) -> ColumnElement:
        return self.make_workplace_filter(identification) & (
            self.conversation_model.assigned_workplace_id == Workplace.id
        )

    def make_customer_conversations_filter(
        self, identification: CustomerIdentification
    ) -> ColumnElement:
        return self.make_customer_filter(identification) & (
            self.conversation_model.customer_id == self.customer_model.id
        )

    def make_agent_conversations_filter(self, identification: AgentIdentification) -> ColumnElement:
        return (
            self.make_agent_filter(identification)
            & (self.conversation_model.assigned_workplace_id == self.workplace_model.id)
            & (self.workplace_model.agent_id == self.agent_model.id)
        )

    def make_conversations_filter(
        self, conversation_ids: List[Any], unassigned_only: bool = False
    ) -> ColumnElement:
        result = self.conversation_model.id.in_(conversation_ids)
        if unassigned_only:
            result = result & (self.conversation_model.assigned_workplace_id == None)  # noqa
        return result

    def make_conversation_options(self, with_messages: bool) -> List[LoaderOption]:
        result: List[LoaderOption] = [
            joinedload(self.conversation_model.customer),
            selectinload(self.conversation_model.tags).joinedload(self.tag_model.created_by),
            joinedload(self.conversation_model.assigned_workplace).joinedload(
                self.workplace_model.agent
            ),
        ]
        if with_messages:
            result.append(selectinload(self.conversation_model.messages))
        return result

    def make_conversation_update_values(self, diff: ConversationDiff) -> Mapping[str, Any]:
        result: Dict[str, Any] = {}

        if diff.state is not None:
            result["state"] = diff.state

        if diff.assigned_workplace_id is SetNone:
            result["assigned_workplace_id"] = None
        elif diff.assigned_workplace_id is not None:
            result["assigned_workplace_id"] = diff.assigned_workplace_id

        if diff.customer_rating is not None:
            result["customer_rating"] = diff.customer_rating

        return result

    def convert_to_event_model(self, event: EventInterface) -> Event:
        return self.event_model(
            kind=event.kind,
            time_utc=event.time_utc.astimezone(timezone.utc),
            agent_id=event.agent_id,
            conversation_id=event.conversation_id,
            customer_id=event.customer_id,
            message_kind=event.message_kind,
            message_media_kind=event.message_media_kind,
            tag_id=event.tag_id,
            workplace_id=event.workplace_id,
        )

    def convert_from_event_model(self, event: Event) -> EventInterface:
        return EventInterface(
            kind=event.kind,
            time_utc=event.time_utc.replace(tzinfo=timezone.utc),
            agent_id=event.agent_id,
            conversation_id=event.conversation_id,
            customer_id=event.customer_id,
            message_kind=event.message_kind,
            message_media_kind=event.message_media_kind,
            tag_id=event.tag_id,
            workplace_id=event.workplace_id,
        )
