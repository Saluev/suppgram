import abc
from typing import Any, Callable, Set

import pytest
import pytest_asyncio

from suppgram.entities import (
    CustomerIdentification,
    Agent,
    Customer,
    Conversation,
)
from suppgram.frontends.telegram import TelegramStorage
from suppgram.frontends.telegram.storage import (
    TelegramChat,
    TelegramChatRole,
    TelegramMessageKind,
    TelegramMessage,
)
from suppgram.storage import Storage
from tests.storage import StorageTestSuiteFixtures


class TelegramStorageTestSuite(StorageTestSuiteFixtures, abc.ABC):
    telegram_storage: TelegramStorage
    storage: Storage

    @abc.abstractmethod
    def generate_id(self) -> Any:
        pass

    @pytest.fixture(autouse=True)
    def _make_generate_telegram_id(self, generate_telegram_id: Callable[[], int]):
        self.generate_telegram_id = generate_telegram_id

    @pytest_asyncio.fixture(scope="function")
    async def group(self) -> TelegramChat:
        return await self.telegram_storage.create_or_update_chat(self.generate_telegram_id())

    @pytest.mark.asyncio
    async def test_get_non_existing_group(self):
        with pytest.raises(Exception):
            await self.telegram_storage.get_chat(self.generate_telegram_id())

    @pytest.mark.asyncio
    async def test_create_or_update_group(self):
        telegram_chat_id = self.generate_telegram_id()
        group = await self.telegram_storage.create_or_update_chat(telegram_chat_id)
        assert group.telegram_chat_id == telegram_chat_id
        assert group.roles == set()

    @pytest.mark.asyncio
    async def test_add_non_existing_group_roles(self):
        with pytest.raises(Exception):
            await self.telegram_storage.add_chat_roles(self.generate_telegram_id())

    @pytest.mark.asyncio
    async def test_add_group_roles(self, group: TelegramChat):
        await self.telegram_storage.add_chat_roles(
            group.telegram_chat_id, TelegramChatRole.AGENTS
        )
        group = await self.telegram_storage.get_chat(group.telegram_chat_id)
        assert group.roles == {TelegramChatRole.AGENTS}

        await self.telegram_storage.add_chat_roles(
            group.telegram_chat_id, TelegramChatRole.NEW_CONVERSATION_NOTIFICATIONS
        )
        group = await self.telegram_storage.get_chat(group.telegram_chat_id)
        assert group.roles == {
            TelegramChatRole.AGENTS,
            TelegramChatRole.NEW_CONVERSATION_NOTIFICATIONS,
        }

    @pytest.mark.asyncio
    async def test_get_groups_by_role(self):
        g1 = await self.telegram_storage.create_or_update_chat(self.generate_telegram_id())
        g2 = await self.telegram_storage.create_or_update_chat(self.generate_telegram_id())
        await self.telegram_storage.add_chat_roles(g2.telegram_chat_id, TelegramChatRole.AGENTS)

        groups = await self.telegram_storage.get_chats_by_role(TelegramChatRole.AGENTS)
        group_ids = {g.telegram_chat_id for g in groups}
        assert g1.telegram_chat_id not in group_ids
        assert g2.telegram_chat_id in group_ids
        # Not checking for equality because of side effects of other tests.

    @pytest.mark.asyncio
    async def test_get_non_existing_message(self, group: TelegramChat):
        with pytest.raises(Exception):
            await self.telegram_storage.get_message(group, self.generate_telegram_id())

    @pytest.mark.asyncio
    async def test_insert_message(
        self,
        group: TelegramChat,
        # Following entities are necessary to avoid foreign key constraint failure:
        agent: Agent,
        customer: Customer,
        conversation: Conversation,
    ):
        telegram_bot_id = self.generate_telegram_id()
        telegram_message_id = self.generate_telegram_id()

        message = await self.telegram_storage.insert_message(
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
        assert message.chat.telegram_chat_id == group.telegram_chat_id
        assert message.telegram_message_id == telegram_message_id
        assert message.agent_id == agent.id
        assert message.customer_id == customer.id
        assert message.conversation_id == conversation.id
        assert message.telegram_bot_username == "MyTestBot"
        message_id = message.id

        message = await self.telegram_storage.get_message(group, telegram_message_id)
        assert message.id == message_id

    @pytest.mark.asyncio
    async def test_delete_messages(self, group: TelegramChat):
        m1 = await self._generate_message(
            group, TelegramMessageKind.NUDGE_TO_START_BOT_NOTIFICATION
        )
        m2 = await self._generate_message(
            group, TelegramMessageKind.NUDGE_TO_START_BOT_NOTIFICATION
        )
        await self.telegram_storage.delete_messages([m1])
        with pytest.raises(Exception):
            await self.telegram_storage.get_message(group, m1.telegram_message_id)
        assert await self.telegram_storage.get_message(group, m2.telegram_message_id)

    @pytest.mark.asyncio
    async def test_get_messages_with_filters(
        self,
        group: TelegramChat,
        # Following entities are necessary to avoid foreign key constraint failure:
        agent: Agent,
        customer: Customer,
        conversation: Conversation,
    ):
        b = self.generate_telegram_id()
        g = group
        i = self.generate_telegram_id
        k1 = TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION
        k2 = TelegramMessageKind.NUDGE_TO_START_BOT_NOTIFICATION
        k3 = TelegramMessageKind.RATE_CONVERSATION

        conv = conversation
        cus2 = await self.storage.create_or_update_customer(
            CustomerIdentification(telegram_user_id=self.generate_telegram_id())
        )
        conv2 = await self.storage.get_or_create_conversation(cus2)

        m1 = await self.telegram_storage.insert_message(b, g, i(), k1)
        m2 = await self.telegram_storage.insert_message(b, g, i(), k1, conversation_id=conv.id)
        m3 = await self.telegram_storage.insert_message(b, g, i(), k1, conversation_id=conv2.id)
        m4 = await self.telegram_storage.insert_message(b, g, i(), k2, conversation_id=conv.id)
        m5 = await self.telegram_storage.insert_message(b, g, i(), k2, agent_id=agent.id)
        m6 = await self.telegram_storage.insert_message(b, g, i(), k3, customer_id=customer.id)
        m7 = await self.telegram_storage.insert_message(b, g, i(), k3, customer_id=cus2.id)
        m8 = await self.telegram_storage.insert_message(b, g, i(), k3, telegram_bot_username="foo")
        m9 = await self.telegram_storage.insert_message(b, g, i(), k1, telegram_bot_username="bar")
        # We'll need to check against all_ids below because the database
        # is not cleared between tests for performance reasons.
        all_ids = collect_ids(m1, m2, m3, m4, m5, m6, m7, m8, m9)

        messages = await self.telegram_storage.get_messages(k1)
        assert collect_ids(*messages) & all_ids == collect_ids(m1, m2, m3, m9)

        messages = await self.telegram_storage.get_messages(k1, conversation_id=conversation.id)
        assert collect_ids(*messages) & all_ids == collect_ids(m2)

        messages = await self.telegram_storage.get_messages(k2)
        assert collect_ids(*messages) & all_ids == collect_ids(m4, m5)

        messages = await self.telegram_storage.get_messages(k2, agent_id=agent.id)
        assert collect_ids(*messages) & all_ids == collect_ids(m5)

        messages = await self.telegram_storage.get_messages(k3)
        assert collect_ids(*messages) & all_ids == collect_ids(m6, m7, m8)

    @pytest.mark.asyncio
    async def test_get_newer_messages_of_kind(self, group: TelegramChat):
        await self._generate_message(group, TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION)
        await self._generate_message(group, TelegramMessageKind.NUDGE_TO_START_BOT_NOTIFICATION)
        m3 = await self._generate_message(group, TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION)
        await self._generate_message(group, TelegramMessageKind.NUDGE_TO_START_BOT_NOTIFICATION)
        m5 = await self._generate_message(group, TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION)

        g2 = await self.telegram_storage.create_or_update_chat(self.generate_telegram_id())
        m6 = await self._generate_message(g2, TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION)
        m7 = await self._generate_message(g2, TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION)

        messages = await self.telegram_storage.get_newer_messages_of_kind([m3, m6])
        assert collect_ids(*messages) == collect_ids(m5, m7)

    async def _generate_message(
        self,
        group: TelegramChat,
        kind: TelegramMessageKind,
    ) -> TelegramMessage:
        return await self.telegram_storage.insert_message(
            self.generate_telegram_id(), group, self.generate_telegram_id(), kind
        )


def collect_ids(*messages: TelegramMessage) -> Set[Any]:
    return {m.id for m in messages}
