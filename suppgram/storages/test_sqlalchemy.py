import asyncio
import os
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from suppgram.entities import (
    UserIdentification,
    WorkplaceIdentification,
    AgentIdentification,
)
from suppgram.interfaces import (
    PersistentStorage,
)
from suppgram.storages.sqlalchemy import SQLAlchemyStorage

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def sqlite_engine() -> AsyncEngine:
    with TemporaryDirectory() as dir:
        filename = os.path.join(dir, "test.db")
        yield create_async_engine(f"sqlite+aiosqlite:///{filename}", echo=True)


@pytest.fixture
def storage(sqlite_engine) -> PersistentStorage:
    storage = SQLAlchemyStorage(sqlite_engine)
    asyncio.run(storage.initialize())
    return storage


@pytest.mark.asyncio
async def test_get_or_create_user(storage):
    user = await storage.get_or_create_user(UserIdentification(telegram_user_id=100500))
    assert user.id
    assert user.telegram_user_id == 100500


@pytest.mark.asyncio
async def test_create_and_get_agent(storage):
    await storage.create_agent(AgentIdentification(telegram_user_id=100500))
    agent = await storage.get_agent(AgentIdentification(telegram_user_id=100500))


@pytest.mark.asyncio
async def test_get_agent_conversation(storage):
    await storage.get_or_create_workplace(
        WorkplaceIdentification(
            telegram_user_id=1, telegram_bot_id=2, telegram_chat_id=1
        )
    )


@pytest.mark.asyncio
async def test_get_or_start_conversation(storage):
    user = await storage.get_or_create_user(UserIdentification(telegram_user_id=100500))
    await storage.get_or_start_conversation(user, "foo", ["bar"])
