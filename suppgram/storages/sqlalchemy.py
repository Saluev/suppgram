from typing import List, Any, TypeVar, Type, Tuple

from sqlalchemy import Integer, ForeignKey, Enum, String, and_, ColumnElement
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import (
    declarative_base,
    Mapped,
    mapped_column,
    relationship,
)

from suppgram.entities import (
    UserIdentification,
    User as UserInterface,
    Agent as AgentInterface,
    WorkplaceIdentification,
    Workplace as WorkplaceInterface,
    MessageFrom,
    Message as ConversaionMessageInterface,
    Conversation as ConversationInterface,
)
from suppgram.errors import ConversationNotFound
from suppgram.interfaces import (
    PersistentStorage,
)

Base = declarative_base()


class User(Base):
    __tablename__ = "suppgram_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer)
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="user")


class Agent(Base):
    __tablename__ = "suppgram_agents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer)
    workplaces: Mapped[List["Workplace"]] = relationship(back_populates="agent")
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="assigned_agent"
    )


class Workplace(Base):
    __tablename__ = "suppgram_workplaces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey(Agent.id))
    agent: Mapped[Agent] = relationship(back_populates="workplaces")
    telegram_bot_id: Mapped[int] = mapped_column(Integer)


class Conversation(Base):
    __tablename__ = "suppgram_conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(User.id))
    user: Mapped[User] = relationship(back_populates="conversations")
    assigned_workplace_id: Mapped[int] = mapped_column(ForeignKey(Workplace.id))
    assigned_workplace: Mapped[Workplace] = relationship()
    state_id: Mapped[str] = mapped_column(String, nullable=False)
    messages: Mapped[List["ConversationMessage"]] = relationship(
        back_populates="conversation"
    )


class ConversationMessage(Base):
    __tablename__ = "suppgram_conversation_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey(Conversation.id))
    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    from_: Mapped[MessageFrom] = mapped_column(Enum(MessageFrom), nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)


T = TypeVar("T", bound=Base)


class SQLAlchemyStorage(PersistentStorage):
    def __init__(
        self,
        engine: AsyncEngine,
        user_model: Type = User,
        agent_model: Type = Agent,
        workplace_model: Type = Workplace,
        conversation_model: Type = Conversation,
        conversation_message_model: Type = ConversationMessage,
    ):
        self._engine = engine
        self._session = async_sessionmaker(bind=engine)
        self._user_model = user_model
        self._agent_model = agent_model
        self._workplace_model = workplace_model
        self._conversation_model = conversation_model
        self._conversation_message_model = conversation_message_model

    async def initialize(self):
        await super().initialize()
        tables_to_create = [
            built_in_model.__table__
            for model, built_in_model in [
                (self._user_model, User),
                (self._agent_model, Agent),
                (self._workplace_model, Workplace),
                (self._conversation_model, Conversation),
                (self._conversation_message_model, ConversationMessage),
            ]
            if model is built_in_model
        ]
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=tables_to_create)

    async def get_or_create_user(
        self, identification: UserIdentification
    ) -> UserInterface:
        async with self._session() as session, session.begin():
            user = await (
                session.query(User)
                .filter(self._make_user_filter(identification))
                .first()
            )
            if user is None:
                user = self._make_model(identification, User)
                session.add(user)
                await session.flush()
                await session.refresh(user)
            return self._convert_user(user)

    def _convert_user(self, user: User) -> UserInterface:
        return UserInterface(telegram_user_id=user.telegram_user_id, id=user.id)

    async def get_workplace(
        self, identification: WorkplaceIdentification
    ) -> WorkplaceInterface:
        raise NotImplementedError

    async def create_agent_and_workplace(
        self, identification: WorkplaceIdentification
    ) -> Tuple[AgentInterface, WorkplaceInterface]:
        raise NotImplementedError

    async def get_or_start_conversation(
        self, user: User, starting_state_id: str, closed_state_ids: List[str]
    ) -> ConversationInterface:
        async with self._session() as session, session.begin():
            conv = await (
                session.query(Conversation)
                .filter(
                    (Conversation.user_id == user.id)
                    & (~Conversation.state_id.in_(closed_state_ids))
                )
                .first()
            )
            if conv is None:
                conv = Conversation(
                    user_id=user.id,
                    state_id=starting_state_id,
                )
                session.add(conv)
                await session.flush()
                await session.refresh(conv)
            return ConversationInterface(
                id=conv.id,
                state_id=conv.state_id,
                user=self._convert_user(conv.user),
            )

    async def get_agent_conversation(
        self, identification: WorkplaceIdentification
    ) -> Conversation:
        try:
            async with self._session() as session, session.begin():
                conv, _, _ = await (
                    session.query(Conversation, Workplace, Agent)
                    .filter(
                        self._make_workplace_filter(identification)
                        & (Conversation.assigned_workplace_id == Workplace.id)
                    )
                    .one()
                )
                return conv
        except NoResultFound as exc:
            raise ConversationNotFound() from exc

    async def save_message(
        self, conversation: ConversationInterface, message: ConversaionMessageInterface
    ):
        async with self._session() as session, session.begin():
            session.add(
                ConversationMessage(
                    conversation_id=conversation.id,
                    from_=message.from_,
                    text=message.text,
                )
            )

    def _make_user_filter(self, identification: UserIdentification) -> ColumnElement:
        return self._make_filter(identification, User)

    def _make_workplace_filter(
        self, identification: WorkplaceIdentification
    ) -> ColumnElement:
        # TODO more generic
        return (Workplace.telegram_bot_id == identification.telegram_bot_id) & (
            Agent.telegram_user_id == identification.telegram_user_id
        )

    def _make_model(self, dc: Any, model: Type[T]) -> T:
        return model(**dc.__dict__)

    def _make_filter(self, dc: Any, model: Type[T]) -> ColumnElement:
        return and_(
            *(getattr(model, k) == v for k, v in dc.__dict__.items() if v is not None)
        )
