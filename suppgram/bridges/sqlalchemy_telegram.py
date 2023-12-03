import operator
from functools import reduce
from typing import Optional, Any, List, Iterable

from sqlalchemy import Integer, ForeignKey, Enum, select, update, ColumnElement
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column, relationship, joinedload

from suppgram.frontends.telegram.interfaces import (
    TelegramStorage,
    TelegramGroup as TelegramGroupInterface,
    TelegramMessage as TelegramMessageInterface,
    TelegramMessageKind,
    TelegramGroupRole,
)
from suppgram.storages.sqlalchemy.models import Base, Conversation


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
    group: Mapped[TelegramGroup] = relationship(back_populates="messages")
    telegram_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[TelegramMessageKind] = mapped_column(
        Enum(TelegramMessageKind), nullable=False
    )
    conversation_id: Mapped[int] = mapped_column(ForeignKey(Conversation.id))


class SQLAlchemyTelegramBridge(TelegramStorage):
    def __init__(
        self,
        engine: AsyncEngine,
        group_model: Any = TelegramGroup,
        message_model: Any = TelegramMessage,
    ):
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

    async def get_groups_by_role(
        self, role: TelegramGroupRole
    ) -> List[TelegramGroupInterface]:
        async with self._session() as session:
            groups: Iterable[TelegramGroup] = (
                (
                    await session.execute(
                        select(self._group_model).filter(
                            self._group_model.roles.bitwise_and(role.value) != 0
                        )
                    )
                )
                .scalars()
                .all()
            )
        return [self._convert_group(group) for group in groups]

    async def get_group(self, telegram_chat_id: int) -> TelegramGroupInterface:
        async with self._session() as session:
            group = (
                (
                    await session.execute(
                        select(self._group_model).filter(
                            self._group_model.telegram_chat_id == telegram_chat_id
                        )
                    )
                )
                .scalars()
                .one()
            )
            return self._convert_group(group)

    async def upsert_group(self, telegram_chat_id: int) -> TelegramGroupInterface:
        async with self._session() as session, session.begin():
            query = select(self._group_model).filter(
                self._group_model.telegram_chat_id == telegram_chat_id
            )
            group = (await session.execute(query)).scalars().one_or_none()
            if group is None:
                group = TelegramGroup(telegram_chat_id=telegram_chat_id)  # type: ignore
                session.add(group)
            return self._convert_group(group)

    async def add_group_role(self, telegram_chat_id: int, role: TelegramGroupRole):
        async with self._session() as session, session.begin():
            await session.execute(
                update(TelegramGroup)
                .filter(TelegramGroup.telegram_chat_id == telegram_chat_id)
                .values(roles=TelegramGroup.roles.bitwise_or(role.value))
            )

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
        group: TelegramGroupInterface,
        telegram_message_id: int,
        kind: TelegramMessageKind,
        conversation_id: Optional[Any] = None,
    ):
        async with self._session() as session, session.begin():
            session.add(
                self._message_model(
                    group_id=group.telegram_chat_id,
                    telegram_message_id=telegram_message_id,
                    kind=kind,
                    conversation_id=conversation_id,
                )
            )
        return TelegramMessageInterface(
            group=group,
            telegram_message_id=telegram_message_id,
            kind=kind,
            conversation_id=conversation_id,
        )

    async def get_messages(
        self, kind: TelegramMessageKind, conversation_id: Optional[Any] = None
    ) -> List[TelegramMessageInterface]:
        query = self._message_model.kind == kind
        if conversation_id:
            query = query & (self._message_model.conversation_id == conversation_id)
        async with self._session() as session:
            msgs: Iterable[TelegramMessage] = (
                (
                    await session.execute(
                        select(self._message_model)
                        .options(joinedload(self._message_model.group))
                        .filter(query)
                    )
                )
                .scalars()
                .all()
            )
            return [self._convert_message(msg) for msg in msgs]

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
            query = (
                select(self._message_model)
                .options(joinedload(self._message_model.group))
                .filter(filter)
            )
            msgs = (await session.execute(query)).scalars().all()
            return [self._convert_message(msg) for msg in msgs]

    def _filter_newer_messages_of_kind(
        self, message: TelegramMessageInterface
    ) -> ColumnElement:
        return (
            (self._message_model.kind == message.kind)
            & (self._message_model.group_id == message.group.telegram_chat_id)
            & (self._message_model.telegram_message_id > message.telegram_message_id)
        )

    def _convert_message(self, msg: TelegramMessage) -> TelegramMessageInterface:
        return TelegramMessageInterface(
            group=self._convert_group(msg.group),
            telegram_message_id=msg.telegram_message_id,
            kind=msg.kind,
            conversation_id=msg.conversation_id,
        )
