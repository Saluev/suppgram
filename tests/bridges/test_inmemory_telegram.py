from typing import Any
from uuid import uuid4

import pytest_asyncio

from suppgram.bridges.inmemory_telegram import InMemoryTelegramStorage
from suppgram.storages.inmemory import InMemoryStorage
from tests.frontends.telegram.storage import TelegramStorageTestSuite

pytest_plugins = ("pytest_asyncio",)


class TestInMemoryTelegramStorage(TelegramStorageTestSuite):
    @pytest_asyncio.fixture(autouse=True)
    async def _create_storage(self):
        self.telegram_storage = InMemoryTelegramStorage()
        self.storage = InMemoryStorage()
        await self.telegram_storage.initialize()

    def generate_id(self) -> Any:
        return uuid4()
