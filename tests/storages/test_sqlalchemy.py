from typing import Any, Callable

import pytest

from tests.storage import StorageTestSuite

pytest_plugins = ("pytest_asyncio",)


class TestSQLAlchemyStorageWithSQLite(StorageTestSuite):
    @pytest.fixture(autouse=True)
    def _create_storage(self, sqlite_sqlalchemy_storage):
        self.storage = sqlite_sqlalchemy_storage

    @pytest.fixture(autouse=True)
    def _make_generate_id(self, generate_sqlite_id: Callable[[], int]):
        self._generate_id = generate_sqlite_id

    def generate_id(self) -> Any:
        return self._generate_id()


class TestSQLAlchemyStorageWithPostgreSQL(StorageTestSuite):
    @pytest.fixture(autouse=True)
    def _create_storage(self, postgresql_sqlalchemy_storage):
        self.storage = postgresql_sqlalchemy_storage

    @pytest.fixture(autouse=True)
    def _make_generate_id(self, generate_sqlite_id: Callable[[], int]):
        self._generate_id = generate_sqlite_id

    def generate_id(self) -> Any:
        return self._generate_id()
