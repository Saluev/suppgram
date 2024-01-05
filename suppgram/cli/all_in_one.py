import asyncio
import logging
import os
import sys
from typing import Optional

import click
from click import UsageError

from suppgram.builder import Builder
from suppgram.errors import NoStorageSpecified, NoFrontendSpecified
from suppgram.logging import ConfidentialStreamHandler


@click.command()
@click.option(
    "--loglevel",
    type=click.Choice(["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "FATAL", "CRITICAL"]),
    default="INFO",
    help="Log level",
)
@click.option(
    "--sqlalchemy-uri",
    envvar="SQLALCHEMY_URI",
    default=None,
    help="SQLAlchemy connection URI. Alternatively, environment variable SQLALCHEMY_URI may be used",
)
@click.option(
    "--sqlalchemy-uri-file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to file storing SQLAlchemy connection URI. "
    "Alternatively, environment variable SQLALCHEMY_URI may be used",
)
@click.option(
    "--mongodb-uri",
    envvar="MONGODB_URI",
    default=None,
    help="MongoDB connection URI. Alternatively, environment variable MONGODB_URI may be used",
)
@click.option(
    "--mongodb-uri-file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to file storing MongoDB connection URI. Alternatively, environment variable MONGODB_URI may be used",
)
@click.option(
    "--mongodb-database",
    "mongodb_database_name",
    default=None,
    help="MongoDB database name. If not specified, will connect to the default database specified in the URI",
)
@click.option(
    "--texts",
    "texts_class_path",
    default="suppgram.texts.en.EnglishTextProvider",
    show_default=True,
    help="Class with texts",
)
@click.option(
    "--telegram-customer-bot-token-file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to file storing token for Telegram bot serving customers. "
    "Alternatively, environment variable TELEGRAM_CUSTOMER_BOT_TOKEN may be used",
)
@click.option(
    "--telegram-manager-bot-token-file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to file storing token for Telegram manager bot. "
    "Alternatively, environment variable TELEGRAM_MANAGER_BOT_TOKEN may be used",
)
@click.option(
    "--telegram-agent-bot-tokens-file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to file storing token(s) for Telegram bot(s) serving agents. "
    "Alternatively, environment variable TELEGRAM_AGENT_BOT_TOKENS may be used",
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
@click.option(
    "--pubnub-user-id",
    default="support",
    show_default=True,
    help="PubNub user ID to send support messages from",
)
@click.option(
    "--pubnub-channel-group",
    default="support",
    show_default=True,
    help="PubNub channel group containing chats with support",
)
@click.option(
    "--pubnub-message-converter",
    "pubnub_message_converter_class_path",
    default="suppgram.frontends.pubnub.DefaultMessageConverter",
    show_default=True,
    help="Class converting messages between PubNub JSONs and suppgram.entities.Message objects",
)
def run_all_in_one(
    loglevel: str,
    sqlalchemy_uri: Optional[str],
    sqlalchemy_uri_file: Optional[str],
    mongodb_uri: Optional[str],
    mongodb_uri_file: Optional[str],
    mongodb_database_name: Optional[str],
    texts_class_path: str,
    telegram_customer_bot_token_file: Optional[str],
    telegram_manager_bot_token_file: Optional[str],
    telegram_agent_bot_tokens_file: Optional[str],
    telegram_owner_id: Optional[int],
    customer_shell: bool,
    pubnub_user_id: str,
    pubnub_channel_group: str,
    pubnub_message_converter_class_path: str,
):
    telegram_customer_bot_token: Optional[str] = os.environ.get(
        "TELEGRAM_CUSTOMER_BOT_TOKEN"
    ) or _read_secret_from_file(telegram_customer_bot_token_file)

    telegram_manager_bot_token: Optional[str] = os.environ.get(
        "TELEGRAM_MANAGER_BOT_TOKEN"
    ) or _read_secret_from_file(telegram_manager_bot_token_file)

    telegram_agent_bot_tokens_joined: Optional[str] = os.environ.get(
        "TELEGRAM_AGENT_BOT_TOKENS"
    ) or _read_secret_from_file(telegram_agent_bot_tokens_file)
    telegram_agent_bot_tokens = (
        telegram_agent_bot_tokens_joined.split() if telegram_agent_bot_tokens_joined else []
    )

    replacements = {}
    if telegram_customer_bot_token:
        replacements[telegram_customer_bot_token] = "__CUSTOMER_BOT_TOKEN__"
    if telegram_manager_bot_token:
        replacements[telegram_manager_bot_token] = "__MANAGER_BOT_TOKEN__"
    for i, token in enumerate(telegram_agent_bot_tokens):
        replacements[token] = f"__AGENT_BOT_TOKEN_{i}__"
    logging.basicConfig(
        level=getattr(logging, loglevel),
        handlers=[ConfidentialStreamHandler(sys.stderr, replacements)],
    )

    builder = Builder()

    if sqlalchemy_uri_file:
        if sqlalchemy_uri:
            raise UsageError(
                "both --sqlalchemy-uri (or SQLALCHEMY_URI environment variable) "
                "and --sqlalchemy-uri-file are specified; unclear which URI to use."
            )

        sqlalchemy_uri = _read_secret_from_file(sqlalchemy_uri_file)

    try:
        if sqlalchemy_uri:
            builder = builder.with_sqlalchemy_storage(sqlalchemy_uri)
    except ImportError as exc:
        raise UsageError(
            "can't import SQLAlchemy integration. "
            "Make sure that necessary dependencies are installed:\n\n    pip install suppgram[sqlalchemy]\n"
        ) from exc

    if mongodb_uri_file:
        if mongodb_uri:
            raise UsageError(
                "both --mongodb-uri (or MONGODB_URI environment variable) "
                "and --mongodb-uri-file are specified; unclear which URI to use."
            )

        mongodb_uri = _read_secret_from_file(mongodb_uri_file)

    try:
        if mongodb_uri is not None:
            builder = builder.with_mongodb_storage(mongodb_uri, mongodb_database_name)
    except ImportError as exc:
        raise UsageError(
            "can't import MongoDB integration. "
            "Make sure that necessary dependencies are installed:\n\n    pip install suppgram[mongodb]\n"
        ) from exc

    if texts_class_path:
        builder = builder.with_texts_class_path(texts_class_path)

    try:
        if telegram_manager_bot_token:
            builder = builder.with_telegram_manager_frontend(
                telegram_manager_bot_token, telegram_owner_id
            )

        if telegram_customer_bot_token:
            builder = builder.with_telegram_customer_frontend(telegram_customer_bot_token)

        if telegram_agent_bot_tokens:
            builder = builder.with_telegram_agent_frontend(telegram_agent_bot_tokens)
    except ImportError as exc:
        raise UsageError(
            "can't import Telegram integration. "
            "Make sure that necessary dependencies are installed:\n\n    pip install suppgram[telegram]\n"
        ) from exc

    if customer_shell:
        builder = builder.with_shell_customer_frontend()

    if (
        any(arg.startswith("--pubnub") for arg in sys.argv)
        or "PUBNUB_SUBSCRIBE_KEY" in os.environ
        or "PUBNUB_PUBLISH_KEY" in os.environ
        or "PUBNUB_SECRET_KEY" in os.environ
        or "PUBNUB_TOKEN" in os.environ
    ):
        try:
            from suppgram.frontends.pubnub.errors import MissingCredentials
        except ImportError:
            raise UsageError(
                "can't import PubNub integration. "
                "Make sure that necessary dependencies are installed:\n\n    pip install suppgram[pubnub]\n"
            )

        try:
            builder = builder.with_pubnub_customer_frontend(
                pubnub_user_id=pubnub_user_id,
                pubnub_channel_group=pubnub_channel_group,
                pubnub_message_converter_class_path=pubnub_message_converter_class_path,
            )
        except MissingCredentials as exc:
            raise UsageError(str(exc)) from exc

    try:
        builder.build()
    except NoStorageSpecified as exc:
        raise UsageError(
            "no storage specified. Consider specifying --sqlalchemy-uri or --mongodb-uri parameters."
        ) from exc
    except NoFrontendSpecified as exc:
        raise UsageError(
            "no frontend specified. In this configuration the application is not going to do anything.\n"
            "Consider specifying --telegram-*, --pubnub-* or --customer-shell parameters."
        ) from exc

    loop = asyncio.get_event_loop()
    loop.run_until_complete(builder.start())
    loop.run_forever()


def _read_secret_from_file(path: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    with open(path) as f:
        return f.read().strip()


if __name__ == "__main__":
    run_all_in_one()
