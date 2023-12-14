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
from suppgram.errors import AgentNotFound, WorkplaceNotFound, TagAlreadyExists
from suppgram.storage import Storage


class StorageTestSuite(abc.ABC):
    storage: Storage

    @abc.abstractmethod
    def generate_id(self) -> Any:
        pass

    @pytest.mark.asyncio
    async def test_cant_create_customer_with_id(self):
        with pytest.raises(Exception, match="can't create customer with predefined ID"):
            await self.storage.create_or_update_customer(
                CustomerIdentification(id=self.generate_id())
            )

    @pytest.mark.asyncio
    async def test_create_or_update_telegram_customer(self):
        identification = CustomerIdentification(telegram_user_id=7)
        telegram_customer = await self.storage.create_or_update_customer(identification)
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
            identification,
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
    async def test_cant_create_agent_with_id(self):
        with pytest.raises(Exception, match="can't create agent with predefined ID"):
            await self.storage.create_or_update_agent(AgentIdentification(id=self.generate_id()))

    @pytest.mark.asyncio
    async def test_create_or_update_telegram_agent(self):
        identification = AgentIdentification(telegram_user_id=27)
        telegram_agent = await self.storage.create_or_update_agent(identification)
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
            identification,
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

    @pytest.mark.asyncio
    async def test_cant_create_workplace_with_id(self):
        with pytest.raises(
            Exception, match="should not be called for already existing workplaces with IDs"
        ):
            await self.storage.get_or_create_workplace(
                WorkplaceIdentification(id=self.generate_id())
            )

    @pytest.mark.asyncio
    async def test_cant_create_workplace_for_non_existing_agent(self):
        with pytest.raises(AgentNotFound):
            await self.storage.get_or_create_workplace(
                WorkplaceIdentification(telegram_user_id=47, telegram_bot_id=3)
            )

    @pytest.mark.asyncio
    async def test_get_or_create_telegram_workspace_for_existing_agent(self):
        agent = await self.storage.create_or_update_agent(AgentIdentification(telegram_user_id=57))
        identification = WorkplaceIdentification(telegram_user_id=57, telegram_bot_id=13)
        workplace = await self.storage.get_or_create_workplace(identification)
        assert workplace.telegram_user_id == 57
        assert workplace.telegram_bot_id == 13
        assert workplace.agent.id == agent.id
        workplace_id = workplace.id

        workplace = await self.storage.get_or_create_workplace(
            WorkplaceIdentification(id=workplace_id)
        )
        assert workplace.id == workplace_id

        workplace = await self.storage.get_or_create_workplace(identification)
        assert workplace.id == workplace_id

    @pytest.mark.asyncio
    async def test_get_agent_workplaces(self):
        agent = await self.storage.create_or_update_agent(AgentIdentification(telegram_user_id=67))
        w1 = await self.storage.get_or_create_workplace(
            WorkplaceIdentification(telegram_user_id=67, telegram_bot_id=23)
        )
        w2 = await self.storage.get_or_create_workplace(
            WorkplaceIdentification(telegram_user_id=67, telegram_bot_id=24)
        )

        workplaces = await self.storage.get_agent_workplaces(agent)
        assert len(workplaces) == 2
        assert sorted([w.id for w in workplaces]) == sorted([w1.id, w2.id])

    @pytest.mark.asyncio
    async def test_tags(self):
        tags = await self.storage.find_all_tags()
        assert len(tags) == 0

        agent = await self.storage.create_or_update_agent(AgentIdentification(telegram_user_id=77))
        await self.storage.create_tag("marquee", agent)

        with pytest.raises(TagAlreadyExists):
            await self.storage.create_tag("marquee", agent)

        await self.storage.create_tag("blink", agent)

        tags = await self.storage.find_all_tags()
        assert len(tags) == 2
        assert tags[0].created_by.id == agent.id
        assert sorted([tag.name for tag in tags]) == ["blink", "marquee"]
