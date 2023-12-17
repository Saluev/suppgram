from typing import Any
from uuid import uuid4

import pytest

from suppgram.storages.inmemory import InMemoryStorage
from tests.storage import StorageTestSuite

pytest_plugins = ("pytest_asyncio",)


class TestInMemoryStorage(StorageTestSuite):
    @pytest.fixture(autouse=True)
    def _create_storage(self):
        self.storage = InMemoryStorage()

    def generate_id(self) -> Any:
        return uuid4()
