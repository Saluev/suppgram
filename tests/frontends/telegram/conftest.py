from datetime import datetime, timezone
from itertools import count
from typing import List, Callable, Protocol, Optional, Awaitable
from unittest.mock import Mock
from uuid import uuid4

import pytest
import pytest_asyncio
from telegram import User, Chat, Message, MessageEntity, Update, CallbackQuery, Sticker
from telegram.ext import Application, ApplicationBuilder

from suppgram.backend import Backend
from suppgram.backends.local import LocalBackend
from suppgram.bridges.inmemory_telegram import InMemoryTelegramStorage
from suppgram.entities import (
    CustomerIdentification,
    Conversation,
    CustomerDiff,
    Agent,
    AgentIdentification,
    AgentDiff,
    Workplace,
    WorkplaceIdentification,
    Customer,
)
from suppgram.frontends.telegram import (
    TelegramStorage,
    TelegramCustomerFrontend,
    TelegramAgentFrontend,
)
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.frontends.telegram.helper import TelegramHelper
from suppgram.frontends.telegram.storage import TelegramChat, TelegramChatRole
from suppgram.frontends.telegram.workplace_manager import TelegramWorkplaceManager
from suppgram.storage import Storage
from suppgram.storages.inmemory import InMemoryStorage
from suppgram.texts.en import EnglishTextsProvider


@pytest.fixture
def send_message_mock(mocker) -> Mock:
    return mocker.patch("telegram.ext.ExtBot.send_message")


@pytest.fixture
def edit_message_text_mock(mocker) -> Mock:
    return mocker.patch("telegram.ext.ExtBot.edit_message_text")


@pytest.fixture
def delete_message_mock(mocker) -> Mock:
    return mocker.patch("telegram.ext.ExtBot.delete_message")


@pytest.fixture
def set_my_commands_mock(mocker) -> Mock:
    return mocker.patch("telegram.ext.ExtBot.set_my_commands")


@pytest.fixture
def get_chat_member_mock(mocker) -> Mock:
    return mocker.patch("telegram.ext.ExtBot.get_chat_member")


@pytest.fixture
def customer_bot_token() -> str:
    return "customer_bot"


@pytest.fixture
def agent_bot_tokens() -> List[str]:
    return ["agent_bot_1", "agent_bot_2"]


@pytest.fixture
def manager_bot_token() -> str:
    return "manager_bot"


@pytest.fixture
def app_manager(
    customer_bot_token, agent_bot_tokens, manager_bot_token, generate_telegram_id
) -> TelegramAppManager:
    apps: List[Application] = []
    for token, name in [
        (customer_bot_token, "CustomerBot"),
        *[(token, f"Agent{i}Bot") for i, token in enumerate(agent_bot_tokens)],
        (manager_bot_token, "ManagerBot"),
    ]:
        app = ApplicationBuilder().token(token).build()
        app.bot._initialized = True
        app.bot._bot_user = User(
            id=generate_telegram_id(), first_name=name, is_bot=True, username=name
        )
        apps.append(app)
    return TelegramAppManager(apps)


@pytest.fixture
def customer_app(customer_bot_token, app_manager) -> Application:
    return app_manager.get_app(customer_bot_token)


@pytest.fixture
def agent_apps(agent_bot_tokens, app_manager) -> List[Application]:
    return [app_manager.get_app(token) for token in agent_bot_tokens]


@pytest.fixture
def manager_app(manager_bot_token, app_manager) -> Application:
    return app_manager.get_app(manager_bot_token)


@pytest.fixture
def customer_send_message_mock(mocker, customer_app) -> Mock:
    customer_app.bot._unfreeze()
    return mocker.patch.object(customer_app.bot, "send_message")


@pytest.fixture
def agent_send_message_mocks(mocker, agent_apps) -> List[Mock]:
    for app in agent_apps:
        app.bot._unfreeze()
    return [mocker.patch.object(app.bot, "send_message") for app in agent_apps]


@pytest.fixture
def manager_send_message_mock(mocker, manager_app) -> Mock:
    manager_app.bot._unfreeze()
    return mocker.patch.object(manager_app.bot, "send_message")


@pytest.fixture
def storage() -> Storage:
    return InMemoryStorage()


@pytest.fixture
def telegram_helper(manager_bot_token, app_manager, telegram_storage) -> TelegramHelper:
    return TelegramHelper(
        manager_bot_token=manager_bot_token, app_manager=app_manager, storage=telegram_storage
    )


@pytest.fixture
def telegram_storage() -> TelegramStorage:
    return InMemoryTelegramStorage()


@pytest.fixture
def backend(storage, agent_bot_tokens, app_manager) -> Backend:
    return LocalBackend(
        storage=storage,
        workplace_managers=[TelegramWorkplaceManager(agent_bot_tokens, app_manager)],
    )


@pytest_asyncio.fixture
async def customer_frontend(
    customer_bot_token, app_manager, backend, telegram_storage
) -> TelegramCustomerFrontend:
    frontend = TelegramCustomerFrontend(
        token=customer_bot_token,
        app_manager=app_manager,
        backend=backend,
        storage=telegram_storage,
        texts=EnglishTextsProvider(),
    )
    await frontend.initialize()
    return frontend


@pytest_asyncio.fixture
async def agent_frontend(
    agent_bot_tokens,
    manager_bot_token,
    app_manager,
    backend,
    telegram_helper,
    telegram_storage,
    set_my_commands_mock,
) -> TelegramAgentFrontend:
    frontend = TelegramAgentFrontend(
        agent_bot_tokens=agent_bot_tokens,
        manager_bot_token=manager_bot_token,
        app_manager=app_manager,
        backend=backend,
        helper=telegram_helper,
        storage=telegram_storage,
        texts=EnglishTextsProvider(),
    )
    await frontend.initialize()
    return frontend


@pytest.fixture
def customer_telegram_user(generate_telegram_id) -> User:
    return User(id=generate_telegram_id(), first_name="Best", last_name="customer", is_bot=False)


@pytest.fixture
def customer_telegram_chat(customer_telegram_user) -> Chat:
    return Chat(id=customer_telegram_user.id, type=Chat.PRIVATE)


@pytest_asyncio.fixture
async def customer(
    storage,
    customer_telegram_user,
    customer_frontend,  # to add all handlers to observables
) -> Customer:
    return await storage.create_or_update_customer(
        CustomerIdentification(telegram_user_id=customer_telegram_user.id),
        CustomerDiff(
            telegram_first_name=customer_telegram_user.first_name,
            telegram_last_name=customer_telegram_user.last_name,
            telegram_username=customer_telegram_user.username,
        ),
    )


@pytest_asyncio.fixture
async def customer_conversation(storage, customer) -> Conversation:
    return await storage.get_or_create_conversation(customer)


@pytest.fixture
def agent_telegram_user(generate_telegram_id) -> User:
    return User(
        id=generate_telegram_id(),
        first_name="Agent",
        last_name="007",
        username="agent007",
        is_bot=False,
    )


@pytest.fixture
def agent_telegram_chat(agent_telegram_user) -> Chat:
    return Chat(id=agent_telegram_user.id, type=Chat.PRIVATE)


@pytest_asyncio.fixture
async def agent(
    agent_telegram_user,
    backend,
    agent_frontend,  # to add all handlers to observables
) -> Agent:
    return await backend.create_or_update_agent(
        AgentIdentification(telegram_user_id=agent_telegram_user.id),
        AgentDiff(
            telegram_first_name=agent_telegram_user.first_name,
            telegram_last_name=agent_telegram_user.last_name,
            telegram_username=agent_telegram_user.username,
        ),
    )


@pytest_asyncio.fixture
async def workplaces(agent, agent_apps, backend) -> List[Workplace]:
    return [
        await backend.identify_workplace(
            WorkplaceIdentification(
                telegram_user_id=agent.telegram_user_id,
                telegram_bot_id=agent_app.bot.bot.id,
            )
        )
        for agent_app in agent_apps
    ]


@pytest_asyncio.fixture
async def agent_group(telegram_storage, generate_telegram_id) -> TelegramChat:
    group = await telegram_storage.create_or_update_chat(generate_telegram_id())
    await telegram_storage.add_chat_roles(group.telegram_chat_id, TelegramChatRole.AGENTS)
    return group


@pytest.fixture(scope="session")
def generate_telegram_update_id() -> Callable[[], int]:
    return count(1).__next__


class CustomerUpdateComposer(Protocol):
    def __call__(
        self,
        *,
        chat: Optional[Chat] = None,
        from_user: Optional[User] = None,
        from_customer: bool = False,
        from_workplace: Optional[Workplace] = None,
        to_customer: bool = False,
        to_workplace: Optional[Workplace] = None,
        to_app: Optional[Application] = None,
        text: Optional[str] = None,
        sticker: Optional[Sticker] = None,
        entities: Optional[List[MessageEntity]] = None,
        callback_message: Optional[Message] = None,
        callback_data: Optional[str] = None,
    ) -> Awaitable[Update]:
        pass


@pytest.fixture
def telegram_update(
    customer_app,
    customer_telegram_user,
    customer_telegram_chat,
    agent_apps,
    agent_telegram_user,
    agent_telegram_chat,
    generate_telegram_update_id,
    generate_telegram_id,
    customer_frontend,  # to add all handlers to observables
    agent_frontend,  # to add all handlers to observables
) -> CustomerUpdateComposer:
    async def compose_telegram_update(
        *,
        chat: Optional[Chat] = None,
        from_user: Optional[User] = None,
        from_customer: bool = False,
        from_workplace: Optional[Workplace] = None,
        to_customer: bool = False,
        to_workplace: Optional[Workplace] = None,
        to_app: Optional[Application] = None,
        text: Optional[str] = None,
        sticker: Optional[Sticker] = None,
        entities: Optional[List[MessageEntity]] = None,
        callback_message: Optional[Message] = None,
        callback_data: Optional[str] = None,
    ) -> Update:
        if text == "/start":
            entities = [
                MessageEntity(type=MessageEntity.BOT_COMMAND, offset=0, length=len("/start"))
            ]
        app = to_app
        if from_customer:
            from_user = customer_telegram_user
            chat = customer_telegram_chat
            app = customer_app
        elif from_workplace:
            from_user = agent_telegram_user
            chat = agent_telegram_chat
            app = next(
                app for app in agent_apps if app.bot.bot.id == from_workplace.telegram_bot_id
            )
        elif to_customer:
            from_user = customer_app.bot.bot
            chat = customer_telegram_chat
            app = customer_app
        elif to_workplace:
            app = next(app for app in agent_apps if app.bot.bot.id == to_workplace.telegram_bot_id)
            from_user = app.bot.bot
            chat = agent_telegram_chat
        if text or sticker:
            message = Message(
                message_id=generate_telegram_id(),
                date=datetime.now(timezone.utc),
                chat=chat,
                from_user=from_user,
                text=text,
                sticker=sticker,
                entities=entities,
            )
            message.set_bot(app.bot)
            update = Update(
                update_id=generate_telegram_update_id(),
                message=message,
            )
        elif callback_data:
            update = Update(
                update_id=generate_telegram_update_id(),
                callback_query=CallbackQuery(
                    id=uuid4().hex,
                    from_user=from_user,
                    chat_instance=str(chat.id),
                    data=callback_data,
                    message=callback_message,
                ),
            )
        else:
            assert False, "unsupported arguments to `telegram_update()`"
        update.set_bot(app.bot)
        if not to_customer and not to_workplace:
            await app.process_update(update)
        return update

    return compose_telegram_update
