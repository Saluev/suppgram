import asyncio
from typing import Any, cast

import pytest
import pytest_asyncio
from bson import ObjectId
from motor.core import AgnosticClient, AgnosticDatabase
from motor.motor_asyncio import AsyncIOMotorClient

from suppgram.storage import Storage
from suppgram.storages.mongodb import MongoDBStorage, Collections
from tests.storage import StorageTestSuite

pytest_plugins = ("pytest_asyncio",)


class TestMongoDBStorage(StorageTestSuite):
    @pytest.fixture(scope="session", autouse=True)
    def clean_mongodb_storage(self) -> None:
        # Apparently, `AsyncIOMotorClient` captures event loop on creation.
        # Since event loop is function-scoped in pytest-asyncio, we can't create
        # single client with scope="session". Therefore, we do slow cleanup separately
        # in a session-scoped synchronous fixture and then fast client creation
        # in the function-scoped asynchronous fixture below.
        mongodb_client: AgnosticClient = AsyncIOMotorClient(
            "mongodb://localhost:27017/suppgram_test",
            uuidRepresentation="standard",
        )
        database = cast(AgnosticDatabase, mongodb_client.get_default_database())
        asyncio.ensure_future(mongodb_client.drop_database(database))

    @pytest_asyncio.fixture
    async def mongodb_storage(self) -> Storage:
        mongodb_client: AgnosticClient = AsyncIOMotorClient(
            "mongodb://localhost:27017/suppgram_test",
            uuidRepresentation="standard",
        )
        database = cast(AgnosticDatabase, mongodb_client.get_default_database())
        storage = MongoDBStorage(Collections(database))
        await storage.initialize()
        return storage

    @pytest.fixture(autouse=True)
    def _create_storage(self, mongodb_storage):
        self.storage = mongodb_storage

    def generate_id(self) -> Any:
        return ObjectId()

    def test_create_or_update_shell_customer(self):
        pytest.skip("skipping due to a possible bug in UUID handling by motor")
