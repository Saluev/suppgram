import asyncio
import logging
import sys
from typing import Optional, List

import click

from suppgram.builder import Builder
from suppgram.logging import ConfidentialStreamHandler


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
    "texts_class_path",
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
    "telegram_agent_bot_tokens",
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
@click.option(
    "--customer-shell",
    is_flag=True,
    default=False,
    help="Run shell-based customer interface",
)
def run_all_in_one(
    loglevel: str,
    sqlalchemy_url: Optional[str],
    texts_class_path: str,
    telegram_customer_bot_token: Optional[str],
    telegram_manager_bot_token: Optional[str],
    telegram_agent_bot_tokens: List[str],
    telegram_owner_id: Optional[int],
    customer_shell: bool,
):
    replacements = {}
    if telegram_customer_bot_token:
        replacements[telegram_customer_bot_token] = "<CUSTOMER BOT TOKEN>"
    if telegram_manager_bot_token:
        replacements[telegram_manager_bot_token] = "<MANAGER BOT TOKEN>"
    if telegram_agent_bot_tokens:
        for i, token in enumerate(telegram_agent_bot_tokens):
            replacements[token] = f"<AGENT BOT TOKEN #{i}>"
    logging.basicConfig(
        level=getattr(logging, loglevel),
        handlers=[ConfidentialStreamHandler(sys.stderr, replacements)],
    )

    builder = Builder()

    if sqlalchemy_url:
        builder = builder.with_sqlalchemy_storage(sqlalchemy_url)

    if texts_class_path:
        builder = builder.with_texts_class_path(texts_class_path)

    if telegram_manager_bot_token:
        builder = builder.with_telegram_manager_frontend(
            telegram_manager_bot_token, telegram_owner_id
        )

    if telegram_customer_bot_token:
        builder = builder.with_telegram_customer_frontend(telegram_customer_bot_token)

    if customer_shell:
        builder = builder.with_shell_customer_frontend()

    if telegram_agent_bot_tokens:
        builder = builder.with_telegram_agent_frontend(telegram_agent_bot_tokens)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(builder.start())
    loop.run_forever()


if __name__ == "__main__":
    run_all_in_one()
