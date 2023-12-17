from typing import Any

import pytest_asyncio
from bson import ObjectId

from suppgram.bridges.mongodb_telegram import MongoDBTelegramBridge
from tests.frontends.telegram.storage import TelegramStorageTestSuite

pytest_plugins = ("pytest_asyncio",)


class TestMongoDBTelegramBridge(TelegramStorageTestSuite):
    @pytest_asyncio.fixture(autouse=True)
    async def _create_storage(self, mongodb_database, mongodb_storage):
        self.storage = MongoDBTelegramBridge(mongodb_database)
        self.suppgram_storage = mongodb_storage
        await self.storage.initialize()

    def generate_id(self) -> Any:
        return ObjectId()
