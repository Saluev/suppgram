import abc
from typing import Any
from uuid import uuid4

import pytest

from suppgram.entities import (
    CustomerIdentification,
    CustomerDiff,
    AgentIdentification,
    AgentDiff,
    WorkplaceIdentification,
)
from suppgram.errors import AgentNotFound, WorkplaceNotFound
from suppgram.storage import Storage


class StorageTestSuite(abc.ABC):
    storage: Storage

    @abc.abstractmethod
    def generate_id(self) -> Any:
        pass

    @pytest.mark.asyncio
    async def test_cant_create_with_id(self):
        with pytest.raises(Exception, match="can't create customer with predefined ID"):
            await self.storage.create_or_update_customer(
                CustomerIdentification(id=self.generate_id())
            )

    @pytest.mark.asyncio
    async def test_create_or_update_telegram_customer(self):
        telegram_customer = await self.storage.create_or_update_customer(
            CustomerIdentification(telegram_user_id=7)
        )
        assert telegram_customer.id
        assert telegram_customer.telegram_user_id == 7
        assert telegram_customer.telegram_username is None
        telegram_customer_id = telegram_customer.id

        # Should be able to update by suppgram ID.
        await self.storage.create_or_update_customer(
            CustomerIdentification(id=telegram_customer_id),
            CustomerDiff(telegram_first_name="John"),
        )
        # Should be able to update by Telegram ID.
        telegram_customer = await self.storage.create_or_update_customer(
            CustomerIdentification(telegram_user_id=7),
            CustomerDiff(telegram_last_name="Doe", telegram_username="johndoe"),
        )
        assert telegram_customer.id == telegram_customer_id
        assert telegram_customer.telegram_user_id == 7
        assert telegram_customer.telegram_first_name == "John"
        assert telegram_customer.telegram_last_name == "Doe"
        assert telegram_customer.telegram_username == "johndoe"

    @pytest.mark.asyncio
    async def test_create_or_update_shell_customer(self):
        uuid = uuid4()
        telegram_customer = await self.storage.create_or_update_customer(
            CustomerIdentification(shell_uuid=uuid)
        )
        assert telegram_customer.shell_uuid == uuid

    @pytest.mark.asyncio
    async def test_create_or_update_pubnub_customer(self):
        telegram_customer = await self.storage.create_or_update_customer(
            CustomerIdentification(pubnub_user_id="u", pubnub_channel_id="ch")
        )
        assert telegram_customer.pubnub_user_id == "u"
        assert telegram_customer.pubnub_channel_id == "ch"

    @pytest.mark.asyncio
    async def test_get_non_existing_agent(self):
        with pytest.raises(AgentNotFound):
            await self.storage.get_agent(AgentIdentification(id=self.generate_id()))

        with pytest.raises(AgentNotFound):
            await self.storage.get_agent(AgentIdentification(telegram_user_id=17))

    @pytest.mark.asyncio
    async def test_create_or_update_telegram_agent(self):
        telegram_agent = await self.storage.create_or_update_agent(
            AgentIdentification(telegram_user_id=27)
        )
        assert telegram_agent.id
        assert telegram_agent.telegram_user_id == 27
        assert telegram_agent.telegram_username is None
        telegram_agent_id = telegram_agent.id

        # Should be able to update by suppgram ID.
        await self.storage.update_agent(
            AgentIdentification(id=telegram_agent_id),
            AgentDiff(telegram_first_name="John"),
        )
        # Should be able to update by Telegram ID.
        telegram_agent = await self.storage.update_agent(
            AgentIdentification(telegram_user_id=27),
            AgentDiff(telegram_last_name="Doe", telegram_username="johndoe"),
        )
        assert telegram_agent.id == telegram_agent_id
        assert telegram_agent.telegram_user_id == 27
        assert telegram_agent.telegram_first_name == "John"
        assert telegram_agent.telegram_last_name == "Doe"
        assert telegram_agent.telegram_username == "johndoe"

    @pytest.mark.asyncio
    async def test_get_non_existing_workplace(self):
        with pytest.raises(WorkplaceNotFound):
            await self.storage.get_workplace(WorkplaceIdentification(id=self.generate_id()))

        with pytest.raises(WorkplaceNotFound):
            await self.storage.get_workplace(WorkplaceIdentification(telegram_user_id=37))
