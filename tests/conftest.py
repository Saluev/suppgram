import asyncio
import os
from itertools import count
from tempfile import TemporaryDirectory
from typing import Generator, cast, Callable

import pytest
import pytest_asyncio
from motor.core import AgnosticClient, AgnosticDatabase
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy import event, Engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from suppgram.storage import Storage
from suppgram.storages.mongodb import MongoDBStorage, Collections
from suppgram.storages.sqlalchemy import SQLAlchemyStorage, Models

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


@pytest.fixture(scope="session", autouse=True)
def clean_mongodb_storage() -> None:
    # Apparently, `AsyncIOMotorClient` captures event loop on creation.
    # Since event loop is function-scoped in pytest-asyncio, we can't create
    # single client with scope="session". Therefore, we do slow cleanup separately
    # in a session-scoped synchronous fixture and then fast client creation
    # in the function-scoped asynchronous fixture below.
    mongodb_client: AgnosticClient = AsyncIOMotorClient("mongodb://localhost:27017/suppgram_test")
    database = cast(AgnosticDatabase, mongodb_client.get_default_database())
    asyncio.ensure_future(mongodb_client.drop_database(database))


@pytest_asyncio.fixture
async def mongodb_database() -> AgnosticDatabase:
    mongodb_client: AgnosticClient = AsyncIOMotorClient("mongodb://localhost:27017/suppgram_test")
    return cast(AgnosticDatabase, mongodb_client.get_default_database())


@pytest_asyncio.fixture
async def mongodb_storage(mongodb_database) -> Storage:
    storage = MongoDBStorage(Collections(mongodb_database))
    await storage.initialize()
    return storage


@pytest.fixture(scope="session")
def generate_sqlite_id() -> Callable[[], int]:
    # Not supposed to intersect with any natively generated IDs.
    return count(100000).__next__


@pytest.fixture(scope="session")
def generate_telegram_id() -> Callable[[], int]:
    return count(1).__next__
