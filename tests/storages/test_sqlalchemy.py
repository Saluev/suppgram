import random
from itertools import count
from typing import Any, Callable

import pytest

from tests.storage import StorageTestSuite

pytest_plugins = ("pytest_asyncio",)


class TestSQLAlchemyStorage(StorageTestSuite):
    @pytest.fixture(autouse=True)
    def _create_storage(self, sqlalchemy_storage):
        self.storage = sqlalchemy_storage

    @pytest.fixture(autouse=True)
    def _make_generate_id(self, generate_sqlite_id: Callable[[], int]):
        self._generate_id = generate_sqlite_id

    def generate_id(self) -> Any:
        return self._generate_id()
