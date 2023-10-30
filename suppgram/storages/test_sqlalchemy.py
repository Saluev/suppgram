import os
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy import Engine, create_engine

from suppgram.interfaces import (
    PersistentStorage,
)
from suppgram.entities import UserIdentification, WorkplaceIdentification
from suppgram.storages.sqlalchemy import SQLAlchemyStorage


@pytest.fixture
def sqlite_engine() -> Engine:
    with TemporaryDirectory() as dir:
        filename = os.path.join(dir, "test.db")
        yield create_engine(f"sqlite:///{filename}", echo=True)


@pytest.fixture
def storage(sqlite_engine) -> PersistentStorage:
    return SQLAlchemyStorage(sqlite_engine, create_tables=True)


def test_get_or_create_user(storage):
    user = storage.get_or_create_user(UserIdentification(telegram_user_id=100500))
    assert user.id
    assert user.telegram_user_id == 100500


def test_get_agent_conversation(storage):
    storage.create_agent_and_workplace(
        WorkplaceIdentification(
            telegram_user_id=1, telegram_bot_id=2, telegram_chat_id=1
        )
    )
