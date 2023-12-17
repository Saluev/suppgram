import asyncio
import os
import random
from tempfile import TemporaryDirectory
from typing import Generator, Any

import pytest
from sqlalchemy import event, Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from suppgram.storage import Storage
from suppgram.storages.sqlalchemy import SQLAlchemyStorage, Models
from tests.storage import StorageTestSuite

pytest_plugins = ("pytest_asyncio",)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    # Without this, SQLite will allow violating foreign key
    # constraints and certain tests will fail.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(scope="session")
def sqlite_engine() -> Generator[AsyncEngine, None, None]:
    with TemporaryDirectory() as dir:
        filename = os.path.join(dir, "test.db")
        yield create_async_engine(f"sqlite+aiosqlite:///{filename}", echo=True)


@pytest.fixture(scope="session")
def sqlalchemy_storage(sqlite_engine: AsyncEngine) -> Storage:
    storage = SQLAlchemyStorage(sqlite_engine, Models(sqlite_engine))
    asyncio.run(storage.initialize())
    return storage


class TestSQLAlchemyStorage(StorageTestSuite):
    @pytest.fixture(autouse=True)
    def _create_storage(self, sqlalchemy_storage):
        self.storage = sqlalchemy_storage

    def generate_id(self) -> Any:
        return random.randint(1000, 2**32 - 1)
