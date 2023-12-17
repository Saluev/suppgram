import abc
from typing import Any, Callable

import pytest
import pytest_asyncio

from suppgram.entities import AgentIdentification, CustomerIdentification
from suppgram.frontends.telegram import TelegramStorage
from suppgram.frontends.telegram.storage import (
    TelegramGroup,
    TelegramGroupRole,
    TelegramMessageKind,
    TelegramMessage,
)
from suppgram.storage import Storage


class TelegramStorageTestSuite(abc.ABC):
    storage: TelegramStorage
    suppgram_storage: Storage

    @abc.abstractmethod
    def generate_id(self) -> Any:
        pass

    @pytest.fixture(autouse=True)
    def _make_generate_telegram_id(self, generate_telegram_id: Callable[[], int]):
        self.generate_telegram_id = generate_telegram_id

    @pytest_asyncio.fixture(scope="function")
    async def group(self) -> TelegramGroup:
        return await self.storage.create_or_update_group(self.generate_telegram_id())

    @pytest.mark.asyncio
    async def test_get_non_existing_group(self):
        with pytest.raises(Exception):
            await self.storage.get_group(self.generate_telegram_id())

    @pytest.mark.asyncio
    async def test_create_or_update_group(self):
        telegram_chat_id = self.generate_telegram_id()
        group = await self.storage.create_or_update_group(telegram_chat_id)
        assert group.telegram_chat_id == telegram_chat_id
        assert group.roles == set()

    @pytest.mark.asyncio
    async def test_add_non_existing_group_roles(self):
        with pytest.raises(Exception):
            await self.storage.add_group_roles(self.generate_telegram_id())

    @pytest.mark.asyncio
    async def test_add_group_roles(self, group: TelegramGroup):
        await self.storage.add_group_roles(group.telegram_chat_id, TelegramGroupRole.AGENTS)
        group = await self.storage.get_group(group.telegram_chat_id)
        assert group.roles == {TelegramGroupRole.AGENTS}

        await self.storage.add_group_roles(
            group.telegram_chat_id, TelegramGroupRole.NEW_CONVERSATION_NOTIFICATIONS
        )
        group = await self.storage.get_group(group.telegram_chat_id)
        assert group.roles == {
            TelegramGroupRole.AGENTS,
            TelegramGroupRole.NEW_CONVERSATION_NOTIFICATIONS,
        }

    @pytest.mark.asyncio
    async def test_get_groups_by_role(self):
        g1 = await self.storage.create_or_update_group(self.generate_telegram_id())
        g2 = await self.storage.create_or_update_group(self.generate_telegram_id())
        await self.storage.add_group_roles(g2.telegram_chat_id, TelegramGroupRole.AGENTS)

        groups = await self.storage.get_groups_by_role(TelegramGroupRole.AGENTS)
        group_ids = {g.telegram_chat_id for g in groups}
        assert g1.telegram_chat_id not in group_ids
        assert g2.telegram_chat_id in group_ids
        # Not checking for equality because of side effects of other tests.

    @pytest.mark.asyncio
    async def test_get_non_existing_message(self, group: TelegramGroup):
        with pytest.raises(Exception):
            await self.storage.get_message(group, self.generate_telegram_id())

    @pytest.mark.asyncio
    async def test_insert_message(self, group: TelegramGroup):
        telegram_bot_id = self.generate_telegram_id()
        telegram_message_id = self.generate_telegram_id()

        # These entities are necessary to avoid foreign key constraint failure.
        agent = await self.suppgram_storage.create_or_update_agent(
            AgentIdentification(telegram_user_id=self.generate_telegram_id())
        )
        customer = await self.suppgram_storage.create_or_update_customer(
            CustomerIdentification(telegram_user_id=self.generate_telegram_id())
        )
        conversation = await self.suppgram_storage.get_or_create_conversation(customer)

        message = await self.storage.insert_message(
            telegram_bot_id,
            group,
            telegram_message_id,
            TelegramMessageKind.RATE_CONVERSATION,
            agent_id=agent.id,
            customer_id=customer.id,
            conversation_id=conversation.id,
            telegram_bot_username="MyTestBot",
        )
        assert message.telegram_bot_id == telegram_bot_id
        assert message.group.telegram_chat_id == group.telegram_chat_id
        assert message.telegram_message_id == telegram_message_id
        assert message.agent_id == agent.id
        assert message.customer_id == customer.id
        assert message.conversation_id == conversation.id
        assert message.telegram_bot_username == "MyTestBot"
        message_id = message.id

        message = await self.storage.get_message(group, telegram_message_id)
        assert message.id == message_id

    @pytest.mark.asyncio
    async def test_delete_messages(self, group: TelegramGroup):
        m1 = await self._generate_message(
            group, TelegramMessageKind.NUDGE_TO_START_BOT_NOTIFICATION
        )
        m2 = await self._generate_message(
            group, TelegramMessageKind.NUDGE_TO_START_BOT_NOTIFICATION
        )
        await self.storage.delete_messages([m1])
        with pytest.raises(Exception):
            await self.storage.get_message(group, m1.telegram_message_id)
        assert await self.storage.get_message(group, m2.telegram_message_id)

    @pytest.mark.asyncio
    async def test_get_newer_messages_of_kind(self, group: TelegramGroup):
        await self._generate_message(group, TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION)
        await self._generate_message(group, TelegramMessageKind.NUDGE_TO_START_BOT_NOTIFICATION)
        m3 = await self._generate_message(group, TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION)
        await self._generate_message(group, TelegramMessageKind.NUDGE_TO_START_BOT_NOTIFICATION)
        m5 = await self._generate_message(group, TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION)

        g2 = await self.storage.create_or_update_group(self.generate_telegram_id())
        m6 = await self._generate_message(g2, TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION)
        m7 = await self._generate_message(g2, TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION)

        messages = await self.storage.get_newer_messages_of_kind([m3, m6])
        message_ids = {m.id for m in messages}
        assert message_ids == {m5.id, m7.id}

    async def _generate_message(
        self, group: TelegramGroup, kind: TelegramMessageKind
    ) -> TelegramMessage:
        return await self.storage.insert_message(
            self.generate_telegram_id(), group, self.generate_telegram_id(), kind
        )
