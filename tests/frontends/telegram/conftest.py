from datetime import datetime, timezone
from itertools import count
from typing import List, Callable, Protocol, Optional, Awaitable
from unittest.mock import Mock
from uuid import uuid4

import pytest
import pytest_asyncio
from telegram import User, Chat, Message, MessageEntity, Update, CallbackQuery
from telegram.ext import Application, ApplicationBuilder

from suppgram.backend import Backend
from suppgram.backends.local import LocalBackend
from suppgram.bridges.inmemory_telegram import InMemoryTelegramStorage
from suppgram.entities import CustomerIdentification, Conversation, CustomerDiff
from suppgram.frontends.telegram import TelegramStorage, TelegramCustomerFrontend
from suppgram.frontends.telegram.app_manager import TelegramAppManager
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
def storage() -> Storage:
    return InMemoryStorage()


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


@pytest.fixture
def customer_telegram_user(generate_telegram_id) -> User:
    return User(id=generate_telegram_id(), first_name="Best", last_name="customer", is_bot=False)


@pytest.fixture
def customer_telegram_chat(customer_telegram_user) -> Chat:
    return Chat(id=customer_telegram_user.id, type=Chat.PRIVATE)


@pytest.fixture(scope="session")
def generate_telegram_update_id() -> Callable[[], int]:
    return count(1).__next__


class UpdateComposer(Protocol):
    def __call__(
        self,
        *,
        from_user: Optional[User] = None,
        from_customer: bool = False,
        from_bot: bool = False,
        text: Optional[str] = None,
        entities: Optional[List[MessageEntity]] = None,
        callback_message: Optional[Message] = None,
        callback_data: Optional[str] = None,
    ) -> Awaitable[Update]:
        pass


@pytest.fixture
def customer_telegram_update(
    customer_app,
    customer_telegram_user,
    customer_telegram_chat,
    generate_telegram_update_id,
    generate_telegram_id,
    customer_frontend,  # to add all handlers to observables
) -> UpdateComposer:
    async def compose_telegram_update(
        *,
        from_user: Optional[User] = None,
        from_customer: bool = False,
        from_bot: bool = False,
        text: Optional[str] = None,
        entities: Optional[List[MessageEntity]] = None,
        callback_message: Optional[Message] = None,
        callback_data: Optional[str] = None,
    ) -> Update:
        if from_customer:
            from_user = customer_telegram_user
        if from_bot:
            from_user = customer_app.bot.bot
        if text:
            message = Message(
                message_id=generate_telegram_id(),
                date=datetime.now(timezone.utc),
                chat=customer_telegram_chat,
                from_user=from_user,
                text=text,
                entities=entities,
            )
            message.set_bot(customer_app.bot)
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
                    chat_instance=str(from_user.id),
                    data=callback_data,
                    message=callback_message,
                ),
            )
        else:
            assert False, "unsupported arguments to `telegram_update()`"
        if not from_bot:
            await customer_app.process_update(update)
        return update

    return compose_telegram_update


@pytest_asyncio.fixture
async def customer_conversation(
    storage,
    customer_telegram_user,
    customer_frontend,  # to add all handlers to observables
) -> Conversation:
    customer = await storage.create_or_update_customer(
        CustomerIdentification(telegram_user_id=customer_telegram_user.id),
        CustomerDiff(
            telegram_first_name=customer_telegram_user.first_name,
            telegram_last_name=customer_telegram_user.last_name,
            telegram_username=customer_telegram_user.username,
        ),
    )
    return await storage.get_or_create_conversation(customer)
