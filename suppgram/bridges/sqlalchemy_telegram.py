import operator
from functools import reduce
from typing import Optional, Any, List

from sqlalchemy import (
    Integer,
    ForeignKey,
    Enum,
    select,
    update,
    ColumnElement,
    String,
    delete,
)
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column, relationship, joinedload

from suppgram.frontends.telegram.interfaces import (
    TelegramStorage,
    TelegramGroup as TelegramGroupInterface,
    TelegramMessage as TelegramMessageInterface,
    TelegramMessageKind,
    TelegramGroupRole,
)
from suppgram.storages.sqlalchemy.models import Base, Conversation, Customer, Agent


class TelegramGroup(Base):
    __tablename__ = "suppgram_telegram_groups"
    telegram_chat_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roles: Mapped[int] = mapped_column(Integer, default=0)
    messages: Mapped[List["TelegramMessage"]] = relationship(back_populates="group")


class TelegramMessage(Base):
    __tablename__ = "suppgram_telegram_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey(TelegramGroup.telegram_chat_id), nullable=False
    )
    telegram_bot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    group: Mapped[TelegramGroup] = relationship(back_populates="messages")
    telegram_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[TelegramMessageKind] = mapped_column(Enum(TelegramMessageKind), nullable=False)
    agent_id: Mapped[int] = mapped_column(ForeignKey(Agent.id), nullable=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey(Customer.id), nullable=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey(Conversation.id), nullable=True)
    telegram_bot_username: Mapped[str] = mapped_column(String, nullable=True)


class SQLAlchemyTelegramBridge(TelegramStorage):
    """Implementation of [TelegramStorage][suppgram.frontends.telegram.TelegramStorage] for SQLAlchemy."""

    def __init__(
        self,
        engine: AsyncEngine,
        group_model: Any = TelegramGroup,
        message_model: Any = TelegramMessage,
    ):
        """
        Parameters:
            engine: asynchronous SQLAlchemy engine
            group_model: SQLAlchemy model for Telegram groups
            message_model: SQLAlchemy model for Telegram messages
        """
        self._engine = engine
        self._session = async_sessionmaker(bind=engine)
        self._group_model = group_model
        self._message_model = message_model

    async def initialize(self):
        await super().initialize()
        tables_to_create = [
            built_in_model.__table__
            for model, built_in_model in [
                (self._group_model, TelegramGroup),
                (self._message_model, TelegramMessage),
            ]
            if model is built_in_model
        ]
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=tables_to_create)

    async def get_groups_by_role(self, role: TelegramGroupRole) -> List[TelegramGroupInterface]:
        select_query = select(self._group_model).filter(
            self._group_model.roles.bitwise_and(role.value) != 0
        )
        async with self._session() as session:
            groups = (await session.execute(select_query)).scalars().all()
            return [self._convert_group(group) for group in groups]

    async def get_group(self, telegram_chat_id: int) -> TelegramGroupInterface:
        select_query = select(self._group_model).filter(
            self._group_model.telegram_chat_id == telegram_chat_id
        )
        async with self._session() as session:
            group = (await session.execute(select_query)).scalars().one()
            return self._convert_group(group)

    async def create_or_update_group(self, telegram_chat_id: int) -> TelegramGroupInterface:
        async with self._session() as session, session.begin():
            query = select(self._group_model).filter(
                self._group_model.telegram_chat_id == telegram_chat_id
            )
            group = (await session.execute(query)).scalars().one_or_none()
            if group is None:
                group = self._group_model(telegram_chat_id=telegram_chat_id)  # type: ignore
                session.add(group)
            return self._convert_group(group)

    async def add_group_roles(self, telegram_chat_id: int, *roles: TelegramGroupRole):
        role_values_or = reduce(operator.or_, (role.value for role in roles))
        update_query = (
            update(TelegramGroup)
            .filter(TelegramGroup.telegram_chat_id == telegram_chat_id)
            .values(roles=TelegramGroup.roles.bitwise_or(role_values_or))
        )
        async with self._session() as session, session.begin():
            await session.execute(update_query)

    def _convert_group(self, group: TelegramGroup) -> TelegramGroupInterface:
        roles: List[TelegramGroupRole] = []
        role, encoded_roles = 1, group.roles
        while encoded_roles:
            if role & encoded_roles:
                roles.append(TelegramGroupRole(role))
                encoded_roles ^= role
            role = role << 1
        return TelegramGroupInterface(
            telegram_chat_id=group.telegram_chat_id, roles=frozenset(roles)
        )

    async def insert_message(
        self,
        telegram_bot_id: int,
        group: TelegramGroupInterface,
        telegram_message_id: int,
        kind: TelegramMessageKind,
        agent_id: Optional[Any] = None,
        customer_id: Optional[Any] = None,
        conversation_id: Optional[Any] = None,
        telegram_bot_username: Optional[str] = None,
    ) -> TelegramMessageInterface:
        async with self._session() as session, session.begin():
            message = self._message_model(
                telegram_bot_id=telegram_bot_id,
                group_id=group.telegram_chat_id,
                telegram_message_id=telegram_message_id,
                kind=kind,
                agent_id=agent_id,
                customer_id=customer_id,
                conversation_id=conversation_id,
                telegram_bot_username=telegram_bot_username,
            )
            session.add(message)
            await session.flush()
            await session.refresh(message)
            return self._convert_message(message, group)

    async def get_message(
        self, group: TelegramGroupInterface, telegram_message_id: int
    ) -> TelegramMessageInterface:
        filter_ = (self._message_model.group_id == group.telegram_chat_id) & (
            self._message_model.telegram_message_id == telegram_message_id
        )
        select_query = (
            select(self._message_model)
            .options(joinedload(self._message_model.group))
            .where(filter_)
        )
        async with self._session() as session:
            msg = (await session.execute(select_query)).scalars().one()
            return self._convert_message(msg, self._convert_group(msg.group))

    async def get_messages(
        self,
        kind: TelegramMessageKind,
        agent_id: Optional[Any] = None,
        conversation_id: Optional[Any] = None,
        telegram_bot_username: Optional[str] = None,
    ) -> List[TelegramMessageInterface]:
        filter_ = self._message_model.kind == kind
        if agent_id is not None:
            filter_ = filter_ & (self._message_model.agent_id == agent_id)
        if conversation_id is not None:
            filter_ = filter_ & (self._message_model.conversation_id == conversation_id)
        if telegram_bot_username:
            filter_ = filter_ & (self._message_model.telegram_bot_username == telegram_bot_username)
        select_query = (
            select(self._message_model)
            .options(joinedload(self._message_model.group))
            .where(filter_)
        )
        async with self._session() as session:
            msgs = (await session.execute(select_query)).scalars().all()
            return [self._convert_message(msg, self._convert_group(msg.group)) for msg in msgs]

    async def delete_messages(self, messages: List[TelegramMessageInterface]):
        message_ids = [message.id for message in messages]
        delete_query = delete(self._message_model).where(self._message_model.id.in_(message_ids))
        async with self._session() as session, session.begin():
            await session.execute(delete_query)

    async def get_newer_messages_of_kind(
        self, messages: List[TelegramMessageInterface]
    ) -> List[TelegramMessageInterface]:
        if not messages:
            return []
        async with self._session() as session:
            filter = reduce(
                operator.or_,
                (self._filter_newer_messages_of_kind(message) for message in messages),
            )
            select_query = (
                select(self._message_model)
                .options(joinedload(self._message_model.group))
                .filter(filter)
            )
            msgs = (await session.execute(select_query)).scalars().all()
            return [self._convert_message(msg, self._convert_group(msg.group)) for msg in msgs]

    def _filter_newer_messages_of_kind(self, message: TelegramMessageInterface) -> ColumnElement:
        return (
            (self._message_model.kind == message.kind)
            & (self._message_model.group_id == message.group.telegram_chat_id)
            & (self._message_model.telegram_message_id > message.telegram_message_id)
        )

    def _convert_message(
        self, msg: TelegramMessage, group: TelegramGroupInterface
    ) -> TelegramMessageInterface:
        return TelegramMessageInterface(
            id=msg.id,
            telegram_bot_id=msg.telegram_bot_id,
            group=group,
            telegram_message_id=msg.telegram_message_id,
            kind=msg.kind,
            customer_id=msg.customer_id,
            conversation_id=msg.conversation_id,
            telegram_bot_username=msg.telegram_bot_username,
        )
