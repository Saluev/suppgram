from dataclasses import replace
from typing import List, Optional, Any
from uuid import uuid4

from suppgram.frontends.telegram import TelegramStorage
from suppgram.frontends.telegram.storage import (
    TelegramMessage,
    TelegramMessageKind,
    TelegramGroup,
    TelegramGroupRole,
)


class InMemoryTelegramStorage(TelegramStorage):
    """In-memory implementation of [Storage][suppgram.storage.Storage] used in tests."""

    def __init__(self) -> None:
        self.groups: List[TelegramGroup] = []
        self.messages: List[TelegramMessage] = []

    async def get_group(self, telegram_chat_id: int) -> TelegramGroup:
        try:
            return next(g for g in self.groups if g.telegram_chat_id == telegram_chat_id)
        except StopIteration:
            raise ValueError

    async def create_or_update_group(self, telegram_chat_id: int) -> TelegramGroup:
        try:
            return await self.get_group(telegram_chat_id)
        except ValueError:
            group = TelegramGroup(telegram_chat_id=telegram_chat_id, roles=frozenset())
            self.groups.append(group)
            return group

    async def add_group_roles(self, telegram_chat_id: int, *roles: TelegramGroupRole):
        try:
            idx = next(
                i for i, g in enumerate(self.groups) if g.telegram_chat_id == telegram_chat_id
            )
        except StopIteration:
            raise ValueError
        group = self.groups.pop(idx)
        group = replace(group, roles=group.roles | {*roles})
        self.groups.append(group)
        return group

    async def get_groups_by_role(self, role: TelegramGroupRole) -> List[TelegramGroup]:
        return [g for g in self.groups if role in g.roles]

    async def insert_message(
        self,
        telegram_bot_id: int,
        group: TelegramGroup,
        telegram_message_id: int,
        kind: TelegramMessageKind,
        *,
        agent_id: Optional[Any] = None,
        customer_id: Optional[Any] = None,
        conversation_id: Optional[Any] = None,
        telegram_bot_username: Optional[str] = None
    ) -> TelegramMessage:
        message = TelegramMessage(
            id=uuid4(),
            telegram_bot_id=telegram_bot_id,
            group=group,
            telegram_message_id=telegram_message_id,
            kind=kind,
            agent_id=agent_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            telegram_bot_username=telegram_bot_username,
        )
        self.messages.append(message)
        return message

    async def get_message(self, group: TelegramGroup, telegram_message_id: int) -> TelegramMessage:
        try:
            return next(
                m
                for m in self.messages
                if m.group.telegram_chat_id == group.telegram_chat_id
                and m.telegram_message_id == telegram_message_id
            )
        except StopIteration:
            raise ValueError

    async def get_messages(
        self,
        kind: TelegramMessageKind,
        *,
        agent_id: Optional[Any] = None,
        conversation_id: Optional[Any] = None,
        telegram_bot_username: Optional[str] = None
    ) -> List[TelegramMessage]:
        return [
            m
            for m in self.messages
            if m.kind == kind
            and (agent_id is None or m.agent_id == agent_id)
            and (conversation_id is None or m.conversation_id == conversation_id)
            and (telegram_bot_username is None or m.telegram_bot_username == telegram_bot_username)
        ]

    async def delete_messages(self, messages: List[TelegramMessage]):
        print(messages, self.messages)
        message_ids = {m.id for m in messages}
        self.messages = [m for m in self.messages if m.id not in message_ids]

    async def get_newer_messages_of_kind(
        self, messages: List[TelegramMessage]
    ) -> List[TelegramMessage]:
        return [
            newer
            for newer in self.messages
            if any(
                newer.group.telegram_chat_id == older.group.telegram_chat_id
                and newer.telegram_message_id > older.telegram_message_id
                and newer.kind == older.kind
                for older in messages
            )
        ]
