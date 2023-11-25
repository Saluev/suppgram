import asyncio
import logging
from importlib import import_module
from typing import Optional, List

import click
from click import UsageError

from suppgram.backend import WorkplaceManager
from suppgram.backends.default import DefaultBackend
from suppgram.entities import AgentIdentification
from suppgram.frontend import (
    CustomerFrontend,
    ManagerFrontend,
    AgentFrontend,
)
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.frontends.telegram.workplace_manager import TelegramWorkplaceManager
from suppgram.permissions import PermissionChecker
from suppgram.storage import Storage
from suppgram.texts.interface import Texts


@click.command()
@click.option(
    "--loglevel",
    type=click.Choice(list(logging.getLevelNamesMapping().keys())),
    default="INFO",
    help="Log level",
)
@click.option(
    "--sqlalchemy-url", default=None, help="URL for SQLAlchemy's `create_engine()`"
)
@click.option(
    "--texts",
    default="suppgram.texts.en.EnglishTexts",
    show_default=True,
    help="Class with texts",
)
@click.option(
    "--telegram-customer-bot-token",
    default=None,
    help="Token for Telegram bot serving customers",
)
@click.option(
    "--telegram-manager-bot-token", default=None, help="Token for Telegram manager bot"
)
@click.option(
    "--telegram-agent-bot-token",
    default=[],
    multiple=True,
    help="Token(s) for Telegram bot(s) serving agents",
)
@click.option(
    "--telegram-owner-id",
    type=int,
    default=None,
    help="ID of Telegram user who will be granted all permissions",
)
def run_all_in_one(
    loglevel: str,
    sqlalchemy_url: Optional[str],
    texts: str,
    telegram_customer_bot_token: Optional[str],
    telegram_manager_bot_token: Optional[str],
    telegram_agent_bot_token: List[str],
    telegram_owner_id: Optional[int],
):
    logging.basicConfig(level=getattr(logging, loglevel))

    storage: Storage
    if sqlalchemy_url:
        from suppgram.storages.sqlalchemy import SQLAlchemyStorage

        from sqlalchemy.ext.asyncio import create_async_engine

        sqlalchemy_engine = create_async_engine(sqlalchemy_url)
        storage = SQLAlchemyStorage(sqlalchemy_engine)
    else:
        raise UsageError(
            "no storage specified. Use --sqlalchemy-url for SQLAlchemy storage"
        )

    telegram_app_manager = TelegramAppManager(
        tokens=list(
            filter(
                None,
                [telegram_customer_bot_token, telegram_manager_bot_token]
                + list(telegram_agent_bot_token),
            )
        )
    )

    texts_module_name, texts_class_name = texts.rsplit(".", 1)
    texts_class = getattr(import_module(texts_module_name), texts_class_name)
    texts_obj: Texts = texts_class()

    permission_checkers: List[PermissionChecker] = []
    if telegram_owner_id:
        from suppgram.frontends.telegram.permission_checkers import (
            TelegramOwnerIDPermissionChecker,
        )

        permission_checkers.append(TelegramOwnerIDPermissionChecker(telegram_owner_id))
    # TODO chat-based permission checker

    workplace_managers: List[WorkplaceManager] = []
    if telegram_agent_bot_token:
        workplace_managers.append(
            TelegramWorkplaceManager(telegram_agent_bot_token, telegram_app_manager)
        )

    backend = DefaultBackend(
        storage=storage,
        permission_checkers=permission_checkers,
        workplace_managers=workplace_managers,
        texts=texts_obj,
    )

    customer_frontend: CustomerFrontend
    if telegram_customer_bot_token:
        from suppgram.frontends.telegram.customer_frontend import (
            TelegramCustomerFrontend,
        )

        customer_frontend = TelegramCustomerFrontend(
            telegram_customer_bot_token, backend, texts_obj
        )
    else:
        raise UsageError(
            "no user frontend specified. Use --telegram-user-bot-token for Telegram frontend"
        )

    manager_frontend: ManagerFrontend
    if telegram_manager_bot_token:
        from suppgram.frontends.telegram.interfaces import TelegramStorage
        from suppgram.frontends.telegram.manager_frontend import TelegramManagerFrontend

        telegram_storage: TelegramStorage
        if sqlalchemy_engine:
            from suppgram.bridges.sqlalchemy_telegram import SQLAlchemyTelegramBridge

            telegram_storage = SQLAlchemyTelegramBridge(sqlalchemy_engine)
            asyncio.run(telegram_storage.initialize())
        else:
            raise UsageError(
                "no storage specified. Use --sqlalchemy-url for SQLAlchemy storage"
            )

        manager_frontend = TelegramManagerFrontend(
            telegram_manager_bot_token, backend, telegram_storage, texts_obj
        )
    else:
        raise UsageError(
            "no manager frontend specified. Use --telegram-manager-bot-token for Telegram frontend"
        )

    agent_frontend: AgentFrontend
    if telegram_agent_bot_token:
        from suppgram.frontends.telegram.agent_frontend import TelegramAgentFrontend

        agent_frontend = TelegramAgentFrontend(
            telegram_agent_bot_token, telegram_app_manager, backend, texts_obj
        )
    else:
        raise UsageError(
            "no agent frontend specified. Use --telegram-agent-bot-token for Telegram frontend"
        )

    async def _run():
        await storage.initialize()
        if telegram_owner_id:
            await backend.create_agent(
                AgentIdentification(telegram_user_id=telegram_owner_id)
            )
        await asyncio.gather(
            customer_frontend.initialize(),
            manager_frontend.initialize(),
            agent_frontend.initialize(),
        )
        await asyncio.gather(
            customer_frontend.start(), manager_frontend.start(), agent_frontend.start()
        )

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_run())
    loop.run_forever()


if __name__ == "__main__":
    run_all_in_one()
