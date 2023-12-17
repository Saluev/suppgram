import abc
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

import pytest
import pytest_asyncio

from suppgram.entities import (
    CustomerIdentification,
    CustomerDiff,
    AgentIdentification,
    AgentDiff,
    WorkplaceIdentification,
    ConversationState,
    ConversationDiff,
    Agent,
    Workplace,
    Customer,
    ConversationTag,
    Conversation,
    Message,
    MessageKind,
    SetNone,
)
from suppgram.errors import (
    AgentNotFound,
    WorkplaceNotFound,
    TagAlreadyExists,
    ConversationNotFound,
    ConversationAlreadyAssigned,
    DataNotFetched,
)
from suppgram.storage import Storage


class StorageTestSuiteFixtures:
    storage: Storage
    generate_telegram_id: Callable[[], int]

    @pytest_asyncio.fixture(scope="function")
    async def customer(self) -> Customer:
        return await self.storage.create_or_update_customer(
            CustomerIdentification(telegram_user_id=self.generate_telegram_id())
        )

    @pytest_asyncio.fixture(scope="function")
    async def conversation(self, customer: Customer) -> Conversation:
        return await self.storage.get_or_create_conversation(customer)

    @pytest_asyncio.fixture(scope="function")
    async def agent(self) -> Agent:
        return await self.storage.create_or_update_agent(
            AgentIdentification(telegram_user_id=self.generate_telegram_id())
        )


class StorageTestSuite(StorageTestSuiteFixtures, abc.ABC):
    storage: Storage

    @abc.abstractmethod
    def generate_id(self) -> Any:
        pass

    @pytest.fixture(autouse=True)
    def _make_generate_telegram_id(self, generate_telegram_id: Callable[[], int]):
        self.generate_telegram_id = generate_telegram_id

    @pytest_asyncio.fixture(scope="function")
    async def workplace(self, agent: Agent) -> Workplace:
        return await self.storage.get_or_create_workplace(
            WorkplaceIdentification(
                telegram_user_id=agent.telegram_user_id, telegram_bot_id=self.generate_telegram_id()
            )
        )

    @pytest_asyncio.fixture(scope="function")
    async def tag1(self, agent: Agent) -> ConversationTag:
        return await self.storage.create_tag(name="urgent", created_by=agent)

    @pytest_asyncio.fixture(scope="function")
    async def tag2(self, agent: Agent) -> ConversationTag:
        return await self.storage.create_tag(name="can wait", created_by=agent)

    @pytest.mark.asyncio
    async def test_cant_create_customer_with_id(self):
        with pytest.raises(Exception, match="can't create customer with predefined ID"):
            await self.storage.create_or_update_customer(
                CustomerIdentification(id=self.generate_id())
            )

    @pytest.mark.asyncio
    async def test_create_or_update_telegram_customer(self):
        telegram_user_id = self.generate_telegram_id()
        identification = CustomerIdentification(telegram_user_id=telegram_user_id)
        telegram_customer = await self.storage.create_or_update_customer(identification)
        assert telegram_customer.id
        assert telegram_customer.telegram_user_id == telegram_user_id
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
        assert telegram_customer.telegram_user_id == telegram_user_id
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
            await self.storage.get_agent(
                AgentIdentification(telegram_user_id=self.generate_telegram_id())
            )

    @pytest.mark.asyncio
    async def test_cant_create_agent_with_id(self):
        with pytest.raises(Exception, match="can't create agent with predefined ID"):
            await self.storage.create_or_update_agent(AgentIdentification(id=self.generate_id()))

    @pytest.mark.asyncio
    async def test_create_or_update_telegram_agent(self):
        telegram_user_id = self.generate_telegram_id()
        identification = AgentIdentification(telegram_user_id=telegram_user_id)
        telegram_agent = await self.storage.create_or_update_agent(identification)
        assert telegram_agent.id
        assert telegram_agent.telegram_user_id == telegram_user_id
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
        assert telegram_agent.telegram_user_id == telegram_user_id
        assert telegram_agent.telegram_first_name == "John"
        assert telegram_agent.telegram_last_name == "Doe"
        assert telegram_agent.telegram_username == "johndoe"

    @pytest.mark.asyncio
    async def test_get_non_existing_workplace(self):
        with pytest.raises(WorkplaceNotFound):
            await self.storage.get_workplace(WorkplaceIdentification(id=self.generate_id()))

        with pytest.raises(WorkplaceNotFound):
            await self.storage.get_workplace(
                WorkplaceIdentification(telegram_user_id=self.generate_telegram_id())
            )

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
                WorkplaceIdentification(
                    telegram_user_id=self.generate_telegram_id(),
                    telegram_bot_id=self.generate_telegram_id(),
                )
            )

    @pytest.mark.asyncio
    async def test_get_or_create_telegram_workspace_for_existing_agent(self, agent: Agent):
        telegram_bot_id = self.generate_telegram_id()
        identification = WorkplaceIdentification(
            telegram_user_id=agent.telegram_user_id, telegram_bot_id=telegram_bot_id
        )
        workplace = await self.storage.get_or_create_workplace(identification)
        assert workplace.telegram_user_id == agent.telegram_user_id
        assert workplace.telegram_bot_id == telegram_bot_id
        assert workplace.agent.id == agent.id
        workplace_id = workplace.id

        workplace = await self.storage.get_or_create_workplace(
            WorkplaceIdentification(id=workplace_id)
        )
        assert workplace.id == workplace_id

        workplace = await self.storage.get_or_create_workplace(identification)
        assert workplace.id == workplace_id

    @pytest.mark.asyncio
    async def test_get_agent_workplaces(self, agent: Agent):
        w1 = await self.storage.get_or_create_workplace(
            WorkplaceIdentification(
                telegram_user_id=agent.telegram_user_id, telegram_bot_id=self.generate_telegram_id()
            )
        )
        w2 = await self.storage.get_or_create_workplace(
            WorkplaceIdentification(
                telegram_user_id=agent.telegram_user_id, telegram_bot_id=self.generate_telegram_id()
            )
        )

        workplaces = await self.storage.get_agent_workplaces(agent)
        assert len(workplaces) == 2
        assert sorted([w.id for w in workplaces]) == sorted([w1.id, w2.id])

    @pytest.mark.asyncio
    async def test_tags(self, agent: Agent):
        tags = await self.storage.find_all_tags()
        assert len(tags) == 0

        await self.storage.create_tag("marquee", agent)

        with pytest.raises(TagAlreadyExists):
            await self.storage.create_tag("marquee", agent)

        await self.storage.create_tag("blink", agent)

        tags = await self.storage.find_all_tags()
        assert len(tags) == 2
        assert tags[0].created_by.id == agent.id
        assert sorted([tag.name for tag in tags]) == ["blink", "marquee"]

    @pytest.mark.asyncio
    async def test_get_non_existing_conversation(self, workplace: Workplace):
        convs = await self.storage.find_conversations_by_ids([self.generate_id()])
        assert convs == []

        with pytest.raises(ConversationNotFound):
            await self.storage.get_agent_conversation(workplace.identification)

    @pytest.mark.asyncio
    async def test_create_conversation(self, customer: Customer):
        conv = await self.storage.get_or_create_conversation(customer)
        assert conv.state == ConversationState.NEW
        assert conv.customer.id == customer.id
        assert conv.tags == []
        assert conv.assigned_workplace is None
        assert conv.messages == []

    @pytest.mark.asyncio
    async def test_get_existing_conversation(self, customer: Customer):
        conv = await self.storage.get_or_create_conversation(customer)
        conversation_id = conv.id

        conv = await self.storage.get_or_create_conversation(customer)
        assert conv.id == conversation_id

        convs = await self.storage.find_conversations_by_ids([conversation_id], with_messages=False)
        assert convs == [conv]
        with pytest.raises(DataNotFetched):
            len(convs[0].messages)

        convs = await self.storage.find_conversations_by_ids([conversation_id], with_messages=True)
        assert convs == [conv]
        assert convs[0].messages == []

        convs = await self.storage.find_customer_conversations(customer, with_messages=False)
        assert convs == [conv]
        with pytest.raises(DataNotFetched):
            len(convs[0].messages)

        convs = await self.storage.find_customer_conversations(customer, with_messages=True)
        assert convs == [conv]
        assert convs[0].messages == []

    @pytest.mark.asyncio
    async def test_update_non_existing_converation(self):
        with pytest.raises(ConversationNotFound):
            await self.storage.update_conversation(self.generate_id(), ConversationDiff())

    @pytest.mark.asyncio
    async def test_update_conversation(self, conversation: Conversation, workplace: Workplace):
        await self.storage.update_conversation(
            conversation.id, ConversationDiff(customer_rating=3), unassigned_only=True
        )
        (updated_conv,) = await self.storage.find_conversations_by_ids([conversation.id])
        assert updated_conv.customer_rating == 3

        await self.storage.update_conversation(
            conversation.id,
            ConversationDiff(state=ConversationState.ASSIGNED, assigned_workplace_id=workplace.id),
        )
        (updated_conv,) = await self.storage.find_conversations_by_ids([conversation.id])
        assert updated_conv.state == ConversationState.ASSIGNED
        assert updated_conv.assigned_workplace.id == workplace.id

        with pytest.raises(ConversationAlreadyAssigned):
            await self.storage.update_conversation(
                conversation.id, ConversationDiff(customer_rating=4), unassigned_only=True
            )

        await self.storage.update_conversation(
            conversation.id, ConversationDiff(assigned_workplace_id=SetNone)
        )
        (updated_conv,) = await self.storage.find_conversations_by_ids([conversation.id])
        assert updated_conv.assigned_workplace is None

    @pytest.mark.asyncio
    async def test_update_conversation_tags(
        self,
        conversation: Conversation,
        workplace: Workplace,
        tag1: ConversationTag,
        tag2: ConversationTag,
    ):
        await self.storage.update_conversation(
            conversation.id, ConversationDiff(removed_tags=[tag2])
        )
        (updated_conv,) = await self.storage.find_conversations_by_ids([conversation.id])
        assert updated_conv.tags == []

        await self.storage.update_conversation(conversation.id, ConversationDiff(added_tags=[tag1]))
        (updated_conv,) = await self.storage.find_conversations_by_ids([conversation.id])
        assert [tag.id for tag in updated_conv.tags] == [tag1.id]

        await self.storage.update_conversation(
            conversation.id, ConversationDiff(removed_tags=[tag1])
        )
        (updated_conv,) = await self.storage.find_conversations_by_ids([conversation.id])
        assert updated_conv.tags == []

    @pytest.mark.asyncio
    async def test_get_agent_conversation(self, conversation: Conversation, workplace: Workplace):
        await self.storage.update_conversation(
            conversation.id, ConversationDiff(assigned_workplace_id=workplace.id)
        )
        conv = await self.storage.get_agent_conversation(workplace.identification)
        assert conv.id == conversation.id

        conv = await self.storage.get_agent_conversation(
            WorkplaceIdentification(
                telegram_user_id=workplace.telegram_user_id,
                telegram_bot_id=workplace.telegram_bot_id,
            )
        )
        assert conv.id == conversation.id

        convs = await self.storage.find_agent_conversations(workplace.agent, with_messages=False)
        assert [c.id for c in convs] == [conv.id]
        with pytest.raises(DataNotFetched):
            len(convs[0].messages)

        convs = await self.storage.find_agent_conversations(workplace.agent, with_messages=True)
        assert convs == [conv]
        assert convs[0].messages == []

    @pytest.mark.asyncio
    async def test_save_message_to_non_existing_conversation(self, customer: Customer):
        conv = Conversation(
            id=self.generate_id(), state=ConversationState.NEW, customer=customer, tags=[]
        )
        message = Message(
            kind=MessageKind.FROM_CUSTOMER,
            time_utc=datetime.now(timezone.utc),
            text="Surprise-surprise!",
        )
        with pytest.raises(ConversationNotFound):
            await self.storage.save_message(conv, message)

    @pytest.mark.asyncio
    async def test_save_message(self, conversation: Conversation):
        message_from_customer = Message(
            kind=MessageKind.FROM_CUSTOMER, time_utc=datetime.now(timezone.utc), text="Hi!"
        )
        await self.storage.save_message(conversation, message_from_customer)
        message_from_agent = Message(
            kind=MessageKind.FROM_AGENT, time_utc=datetime.now(timezone.utc), text="Hello!"
        )
        await self.storage.save_message(conversation, message_from_agent)

        (updated_conv,) = await self.storage.find_conversations_by_ids(
            [conversation.id], with_messages=True
        )
        assert len(updated_conv.messages) == 2
        assert [m.kind for m in updated_conv.messages] == [
            MessageKind.FROM_CUSTOMER,
            MessageKind.FROM_AGENT,
        ]
        assert [m.text for m in updated_conv.messages] == ["Hi!", "Hello!"]
