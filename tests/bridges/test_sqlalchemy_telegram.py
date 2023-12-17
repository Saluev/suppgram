from typing import Any, Callable

import pytest
import pytest_asyncio

from suppgram.bridges.sqlalchemy_telegram import SQLAlchemyTelegramBridge
from tests.frontends.telegram.storage import TelegramStorageTestSuite

pytest_plugins = ("pytest_asyncio",)


class TestSQLAlchemyTelegramBridge(TelegramStorageTestSuite):
    @pytest_asyncio.fixture(autouse=True)
    async def _create_storage(self, sqlite_engine, sqlalchemy_storage):
        # SQLAlchemyStorage implementation is needed for related tables to exist.
        self.telegram_storage = SQLAlchemyTelegramBridge(sqlite_engine)
        self.storage = sqlalchemy_storage
        await self.telegram_storage.initialize()

    @pytest.fixture(autouse=True)
    def _make_generate_id(self, generate_sqlite_id: Callable[[], int]):
        self._generate_id = generate_sqlite_id

    def generate_id(self) -> Any:
        return self._generate_id()
