from typing import Optional, Any, Type

from sqlalchemy import Integer, ForeignKey, Enum
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column, relationship

from suppgram.frontends.telegram.interfaces import (
    TelegramStorage,
    TelegramGroup as TelegramGroupInterface,
    TelegramMessageKind,
    TelegramGroupRole,
)
from suppgram.storages.sqlalchemy import Base, Conversation


class TelegramGroup(Base):
    __tablename__ = "suppgram_telegram_groups"
    telegram_group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roles: Mapped[int] = mapped_column(Integer, default=0)


class TelegramMessage(Base):
    __tablename__ = "suppgram_telegram_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_group_id: Mapped[int] = mapped_column(
        ForeignKey(TelegramGroup.telegram_group_id), nullable=False
    )
    telegram_group: Mapped[TelegramGroup] = relationship(back_populates="messages")
    telegram_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[TelegramMessageKind] = mapped_column(
        Enum(TelegramMessageKind), nullable=False
    )
    conversation_id: Mapped[int] = mapped_column(ForeignKey(Conversation.id))


class SQLAlchemyTelegramStorage(TelegramStorage):
    def __init__(
        self,
        engine: AsyncEngine,
        group_model: Type = TelegramGroup,
        message_model: Type = TelegramMessage,
    ):
        self._engine = engine
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

    async def get_group_by_role(
        self, role: TelegramGroupRole
    ) -> TelegramGroupInterface:
        pass

    async def insert_message(
        self,
        group: TelegramGroupInterface,
        telegram_message_id: int,
        kind: TelegramMessageKind,
        conversation_id: Optional[Any] = None,
    ):
        pass
