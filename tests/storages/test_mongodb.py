from typing import Any

import pytest
from bson import ObjectId

from tests.storage import StorageTestSuite

pytest_plugins = ("pytest_asyncio",)


class TestMongoDBStorage(StorageTestSuite):
    @pytest.fixture(autouse=True)
    def _create_storage(self, mongodb_storage):
        self.storage = mongodb_storage

    def generate_id(self) -> Any:
        return ObjectId()
