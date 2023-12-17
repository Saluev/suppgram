import pytest
from telegram.ext import Application, ApplicationBuilder

from suppgram.backends.local import LocalBackend
from suppgram.bridges.inmemory_telegram import InMemoryTelegramStorage
from suppgram.frontends.telegram import TelegramCustomerFrontend
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.frontends.telegram.workplace_manager import TelegramWorkplaceManager
from suppgram.storages.inmemory import InMemoryStorage
from suppgram.texts.en import EnglishTextsProvider


@pytest.fixture
def telegram_app() -> Application:
    return ApplicationBuilder().token("test").build()


@pytest.fixture
def telegram_app_manager(telegram_app) -> TelegramAppManager:
    return TelegramAppManager([telegram_app])


@pytest.fixture
def telegram_customer_frontend(telegram_app_manager) -> TelegramCustomerFrontend:
    return TelegramCustomerFrontend(
        token="test",
        app_manager=telegram_app_manager,
        backend=LocalBackend(
            storage=InMemoryStorage(),
            workplace_managers=[TelegramWorkplaceManager([], telegram_app_manager)],
        ),
        storage=InMemoryTelegramStorage(),
        texts=EnglishTextsProvider(),
    )


def test_customer_frontend(telegram_customer_frontend):
    pass
