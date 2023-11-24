from typing import (
    List,
    Any,
    TypeVar,
    Type,
    Optional,
    Mapping,
    Collection,
)

from sqlalchemy import (
    Integer,
    ForeignKey,
    Enum,
    String,
    and_,
    ColumnElement,
    select,
    update,
)
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import (
    declarative_base,
    Mapped,
    mapped_column,
    relationship,
    joinedload,
    selectinload,
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
    AgentIdentification,
    ConversationState,
    AgentDiff,
)
from suppgram.errors import (
    ConversationNotFound,
    WorkplaceNotFound,
    AgentNotFound,
    WorkplaceAlreadyAssigned,
)
from suppgram.interfaces import (
    Storage,
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
    telegram_first_name: Mapped[str] = mapped_column(String, nullable=True)
    telegram_last_name: Mapped[str] = mapped_column(String, nullable=True)
    telegram_username: Mapped[str] = mapped_column(String, nullable=True)
    workplaces: Mapped[List["Workplace"]] = relationship(back_populates="agent")


class Workplace(Base):
    __tablename__ = "suppgram_workplaces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey(Agent.id))
    agent: Mapped[Agent] = relationship(back_populates="workplaces")
    telegram_bot_id: Mapped[int] = mapped_column(Integer)
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="assigned_workplace"
    )


class Conversation(Base):
    __tablename__ = "suppgram_conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(User.id))
    user: Mapped[User] = relationship(back_populates="conversations")
    assigned_workplace_id: Mapped[int] = mapped_column(
        ForeignKey(Workplace.id), nullable=True
    )
    assigned_workplace: Mapped[Workplace] = relationship(back_populates="conversations")
    state: Mapped[ConversationState] = mapped_column(
        Enum(ConversationState), nullable=False
    )
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


class SQLAlchemyStorage(Storage):
    def __init__(
        self,
        engine: AsyncEngine,
        user_model: Any = User,
        agent_model: Any = Agent,
        workplace_model: Any = Workplace,
        conversation_model: Any = Conversation,
        conversation_message_model: Any = ConversationMessage,
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
            row = (
                await session.execute(
                    select(self._user_model).filter(
                        self._make_user_filter(identification)
                    )
                )
            ).one_or_none()
            if row is None:
                user = self._make_model(identification, self._user_model)
                session.add(user)
                await session.flush()
                await session.refresh(user)
            else:
                (user,) = row
            return self._convert_user(user)

    async def get_agent(self, identification: AgentIdentification) -> AgentInterface:
        async with self._session() as session:
            agent = (
                (
                    await session.execute(
                        select(self._agent_model).filter(
                            self._make_agent_filter(identification)
                        )
                    )
                )
                .scalars()
                .one_or_none()
            )
            if agent is None:
                raise AgentNotFound(identification)
            return self._convert_agent(agent)

    async def create_agent(self, identification: AgentIdentification) -> AgentInterface:
        async with self._session() as session, session.begin():
            agent = self._make_model(
                identification,
                self._agent_model,
            )
            session.add(agent)
            await session.flush()
            await session.refresh(agent)
            return self._convert_agent(agent)

    async def update_agent(self, diff: AgentDiff):
        async with self._session() as session, session.begin():
            agent = (
                (
                    await session.execute(
                        select(self._agent_model).filter(
                            self._agent_model.id == diff.id
                        )
                    )
                )
                .scalars()
                .one()
            )
            self._update_model(agent, diff)
            session.add(agent)

    async def get_workplace(
        self, identification: WorkplaceIdentification
    ) -> WorkplaceInterface:
        async with self._session() as session:
            row = (
                await session.execute(
                    select(self._workplace_model).filter(
                        self._make_workplace_filter(identification)
                    )
                )
            ).one_or_none()
            if row is None:
                raise WorkplaceNotFound(identification)
            (workplace,) = row
            return workplace

    async def get_agent_workplaces(
        self, agent: AgentInterface
    ) -> List[WorkplaceInterface]:
        async with self._session() as session:
            workplaces = (
                (
                    await session.execute(
                        select(self._workplace_model).filter(
                            self._workplace_model.agent_id == agent.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            return [
                self._convert_workplace(agent, workplace) for workplace in workplaces
            ]

    async def get_or_create_workplace(
        self, agent: AgentInterface, identification: WorkplaceIdentification
    ) -> WorkplaceInterface:
        async with self._session() as session, session.begin():
            row = (
                await session.execute(
                    select(self._workplace_model, self._agent_model).filter(
                        self._make_workplace_filter(identification)
                    )
                )
            ).one_or_none()
            if row is None:
                workplace = self._make_model(
                    identification,
                    self._workplace_model,
                    exclude_fields=("telegram_user_id",),
                    agent_id=agent.id,
                )
                session.add(workplace)
                await session.flush()
                await session.refresh(workplace)
            else:
                workplace, _ = row
            return self._convert_workplace(agent, workplace)

    async def get_or_start_conversation(
        self, user: UserInterface
    ) -> ConversationInterface:
        async with self._session() as session, session.begin():
            conv: Optional[Conversation] = (
                (
                    await session.execute(
                        select(self._conversation_model)
                        .options(
                            joinedload(self._conversation_model.user),
                            joinedload(
                                self._conversation_model.assigned_workplace
                            ).joinedload(self._workplace_model.agent),
                            selectinload(self._conversation_model.messages),
                        )
                        .filter(
                            (self._conversation_model.user_id == user.id)
                            & (
                                ~self._conversation_model.state.in_(
                                    [ConversationState.CLOSED]
                                )
                            )
                        )
                    )
                )
                .scalars()
                .one_or_none()
            )
            if conv is None:
                conv = self._conversation_model(
                    user_id=user.id,
                    state=ConversationState.NEW,
                )
                session.add(conv)
                await session.flush()
                await session.refresh(conv)
                assigned_agent = None
                assigned_workplace = None
                messages = []
            else:
                assigned_agent = (
                    self._convert_agent(conv.assigned_workplace.agent)
                    if conv.assigned_workplace
                    else None
                )
                assigned_workplace = (
                    self._convert_workplace(assigned_agent, conv.assigned_workplace)
                    if conv.assigned_workplace
                    else None
                )
                messages = [self._convert_message(msg) for msg in conv.messages]
            return ConversationInterface(
                id=conv.id,
                state=conv.state,
                user=user,
                assigned_agent=assigned_agent,
                assigned_workplace=assigned_workplace,
                messages=messages,
            )

    async def assign_workplace(
        self,
        conversation_id: Any,
        workplace: WorkplaceInterface,
        new_state: ConversationState,
    ):
        async with self._session() as session, session.begin():
            result = await session.execute(
                update(self._conversation_model)
                .filter(self._conversation_model.assigned_workplace_id == None)
                .values(assigned_workplace_id=workplace.id, state=new_state)
            )
            if result.rowcount == 0:
                raise WorkplaceAlreadyAssigned()

    async def get_agent_conversation(
        self, identification: WorkplaceIdentification
    ) -> ConversationInterface:
        try:
            async with self._session() as session, session.begin():
                conv = (
                    (
                        await session.execute(
                            select(
                                self._conversation_model,
                                self._workplace_model,
                                self._agent_model,
                            )
                            .filter(
                                self._make_workplace_filter(identification)
                                & (
                                    self._conversation_model.assigned_workplace_id
                                    == Workplace.id
                                )
                            )
                            .options(
                                joinedload(self._conversation_model.user),
                                selectinload(self._conversation_model.messages),
                                joinedload(
                                    self._conversation_model.assigned_workplace
                                ).joinedload(self._workplace_model.agent),
                            )
                        )
                    )
                    .scalars()
                    .one()
                )
                return self._convert_conversation(conv)
        except NoResultFound as exc:
            raise ConversationNotFound() from exc

    async def save_message(
        self, conversation: ConversationInterface, message: ConversaionMessageInterface
    ):
        async with self._session() as session, session.begin():
            session.add(
                self._conversation_message_model(
                    conversation_id=conversation.id,
                    from_=message.from_,
                    text=message.text,
                )
            )

    def _convert_user(self, user: User) -> UserInterface:
        return UserInterface(telegram_user_id=user.telegram_user_id, id=user.id)

    def _convert_agent(self, agent: Agent) -> AgentInterface:
        return AgentInterface(
            telegram_user_id=agent.telegram_user_id,
            id=agent.id,
            telegram_first_name=agent.telegram_first_name,
            telegram_last_name=agent.telegram_last_name,
            telegram_username=agent.telegram_username,
        )

    def _convert_workplace(
        self, agent: AgentInterface, workplace: Workplace
    ) -> WorkplaceInterface:
        return WorkplaceInterface(
            id=workplace.id,
            telegram_user_id=agent.telegram_user_id,
            telegram_bot_id=workplace.telegram_bot_id,
            agent=agent,
        )

    def _convert_message(
        self, message: ConversationMessage
    ) -> ConversaionMessageInterface:
        return ConversaionMessageInterface(from_=message.from_, text=message.text)

    def _convert_conversation(
        self,
        conversation: Conversation,
    ) -> ConversationInterface:
        agent = self._convert_agent(conversation.assigned_workplace.agent)
        return ConversationInterface(
            id=conversation.id,
            state=conversation.state,
            user=self._convert_user(conversation.user),
            assigned_agent=agent,
            assigned_workplace=self._convert_workplace(
                agent, conversation.assigned_workplace
            ),
            messages=[
                self._convert_message(message) for message in conversation.messages
            ],
        )

    def _make_user_filter(self, identification: UserIdentification) -> ColumnElement:
        return self._make_filter(identification, self._user_model)

    def _make_agent_filter(self, identification: AgentIdentification) -> ColumnElement:
        return self._make_filter(identification, self._agent_model)

    def _make_workplace_filter(
        self, identification: WorkplaceIdentification
    ) -> ColumnElement:
        # TODO more generic
        return (
            (self._workplace_model.telegram_bot_id == identification.telegram_bot_id)
            & (self._workplace_model.agent_id == self._agent_model.id)
            & (self._agent_model.telegram_user_id == identification.telegram_user_id)
        )

    def _make_model(
        self,
        dc: Any,
        model: Type[T],
        exclude_fields: Collection[str] = (),
        **kwargs: Mapping[str, Any]
    ) -> T:
        params = {**dc.__dict__, **kwargs}
        params = {k: v for k, v in params.items() if k not in exclude_fields}
        return model(**params)

    def _update_model(self, model_instance: Any, diff_dc: Any):
        for k, v in diff_dc.__dict__.items():
            if v is not None:
                setattr(model_instance, k, v)

    def _make_filter(self, dc: Any, model: Type[T]) -> ColumnElement:
        return and_(
            *(getattr(model, k) == v for k, v in dc.__dict__.items() if v is not None)
        )
