import asyncio
import os
from tempfile import TemporaryDirectory
from typing import Generator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from suppgram.entities import (
    CustomerIdentification,
    WorkplaceIdentification,
    AgentIdentification,
)
from suppgram.storage import Storage
from suppgram.storages.sqlalchemy.models import Models
from suppgram.storages.sqlalchemy.storage import SQLAlchemyStorage

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def sqlite_engine() -> Generator[AsyncEngine, None, None]:
    with TemporaryDirectory() as dir:
        filename = os.path.join(dir, "test.db")
        yield create_async_engine(f"sqlite+aiosqlite:///{filename}", echo=True)


@pytest.fixture
def storage(sqlite_engine) -> Storage:
    storage = SQLAlchemyStorage(sqlite_engine, Models(sqlite_engine))
    asyncio.run(storage.initialize())
    return storage


@pytest.mark.asyncio
async def test_get_or_create_user(storage):
    user = await storage.create_or_update_customer(
        CustomerIdentification(telegram_user_id=100500)
    )
    assert user.id
    assert user.telegram_user_id == 100500


@pytest.mark.asyncio
async def test_create_and_get_agent(storage):
    await storage.create_or_update_agent(AgentIdentification(telegram_user_id=100500))
    await storage.get_agent(AgentIdentification(telegram_user_id=100500))


@pytest.mark.asyncio
async def test_get_agent_conversation(storage):
    await storage.get_or_create_workplace(
        WorkplaceIdentification(
            telegram_user_id=1, telegram_bot_id=2, telegram_chat_id=1
        )
    )


@pytest.mark.asyncio
async def test_get_or_start_conversation(storage):
    user = await storage.create_or_update_customer(
        CustomerIdentification(telegram_user_id=100500)
    )
    await storage.get_or_create_conversation(user, "foo", ["bar"])
