from typing import Any, Callable

import pytest
import pytest_asyncio

from suppgram.bridges.sqlalchemy_telegram import SQLAlchemyTelegramBridge
from tests.frontends.telegram.storage import TelegramStorageTestSuite

pytest_plugins = ("pytest_asyncio",)


class TestSQLAlchemyTelegramBridgeWithSQLite(TelegramStorageTestSuite):
    @pytest_asyncio.fixture(autouse=True)
    async def _create_storage(self, sqlite_engine, sqlite_sqlalchemy_storage):
        # SQLAlchemyStorage implementation is needed for related tables to exist.
        self.telegram_storage = SQLAlchemyTelegramBridge(sqlite_engine)
        self.storage = sqlite_sqlalchemy_storage
        await self.telegram_storage.initialize()

    @pytest.fixture(autouse=True)
    def _make_generate_id(self, generate_sqlite_id: Callable[[], int]):
        self._generate_id = generate_sqlite_id

    def generate_id(self) -> Any:
        return self._generate_id()


class TestSQLAlchemyTelegramBridgeWithPostgreSQL(TelegramStorageTestSuite):
    @pytest_asyncio.fixture(autouse=True)
    async def _create_storage(self, postgresql_engine, postgresql_sqlalchemy_storage):
        # SQLAlchemyStorage implementation is needed for related tables to exist.
        self.telegram_storage = SQLAlchemyTelegramBridge(postgresql_engine)
        self.storage = postgresql_sqlalchemy_storage
        await self.telegram_storage.initialize()

    @pytest.fixture(autouse=True)
    def _make_generate_id(self, generate_sqlite_id: Callable[[], int]):
        self._generate_id = generate_sqlite_id

    def generate_id(self) -> Any:
        return self._generate_id()
