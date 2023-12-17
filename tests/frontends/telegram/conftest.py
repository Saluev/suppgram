from typing import List

import pytest
import pytest_asyncio
from telegram import User
from telegram.ext import Application, ApplicationBuilder

from suppgram.backend import Backend
from suppgram.backends.local import LocalBackend
from suppgram.bridges.inmemory_telegram import InMemoryTelegramStorage
from suppgram.frontends.telegram import TelegramStorage, TelegramCustomerFrontend
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.frontends.telegram.workplace_manager import TelegramWorkplaceManager
from suppgram.storage import Storage
from suppgram.storages.inmemory import InMemoryStorage
from suppgram.texts.en import EnglishTextsProvider


@pytest.fixture
def send_message_mock(mocker):
    return mocker.patch("telegram.ext.ExtBot.send_message")


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
