import logging
from importlib import import_module
from typing import Optional, List, Any, Iterable, cast, Union
from uuid import UUID, uuid4

from suppgram.analytics import Reporter
from suppgram.backend import WorkplaceManager, Backend
from suppgram.entities import AgentIdentification
from suppgram.errors import NoStorageSpecified, NoFrontendSpecified
from suppgram.frontend import ManagerFrontend, CustomerFrontend, AgentFrontend
from suppgram.helpers import flat_gather
from suppgram.storage import Storage
from suppgram.texts.en import EnglishTextProvider
from suppgram.texts.interface import TextProvider

logger = logging.getLogger(__name__)


class Builder:
    """Provides a simple interface for building functional
    Suppgram application from separate components."""

    def __init__(self) -> None:
        # Implementation-specific objects are declared as `Any` to
        # avoid importing packages which may have missing dependencies.

        self._initialized = False

        self._storage: Optional[Storage] = None
        self._sqlalchemy_engine: Optional[Any] = None
        self._mongodb_client: Optional[Any] = None
        self._mongodb_database: Optional[Any] = None

        self._texts: Optional[TextProvider] = None

        # Helper classes, including implementation-specific:
        self._telegram_app_manager: Optional[Any] = None
        self._telegram_helper: Optional[Any] = None
        self._telegram_storage: Optional[Any] = None
        self._pubnub_configuration: Optional[Any] = None
        self._pubnub_message_converter: Optional[Any] = None
        self._workplace_managers: List[WorkplaceManager] = []

        self._backend: Optional[Backend] = None

        self._manager_frontend: Optional[ManagerFrontend] = None
        self._telegram_manager_bot_token: Optional[str] = None
        self._telegram_owner_id: Optional[int] = None

        self._customer_frontends: List[CustomerFrontend] = []
        self._telegram_customer_bot_token: Optional[str] = None
        self._shell_customer_uuid: Optional[UUID] = None
        self._pubnub_channel_group: Optional[str] = None

        self._agent_frontends: List[AgentFrontend] = []
        self._telegram_agent_bot_tokens: List[str] = []

    def build(self) -> "Builder":
        """Instantiate all configured components and raise exception if misconfigured."""
        self._build_backend()
        self._build_manager_frontend()
        self._build_customer_frontends()
        self._build_agent_frontends()
        from suppgram.backends.local import LocalBackend

        if (
            not self._customer_frontends
            and not self._agent_frontends
            and self._manager_frontend is None
            and isinstance(self._backend, LocalBackend)
        ):
            raise NoFrontendSpecified()

        return self

    async def start(self):
        """Start all configured components."""
        await self._initialize()
        await flat_gather(runnable.start() for runnable in self._get_runnables())

    def with_storage(self, storage: Storage) -> "Builder":
        """Configure arbitrary [Storage][suppgram.storage.Storage] instance."""
        if self._storage is not None:
            raise ValueError(
                f"can't use {type(storage).__name__} — "
                f"already instantiated {type(self._storage).__name__}"
            )

        self._storage = storage
        return self

    def with_sqlalchemy_storage(self, sqlalchemy_uri: str) -> "Builder":
        """Configure [SQLAlchemyStorage][suppgram.storages.sqlalchemy.SQLAlchemyStorage]."""
        if self._storage is not None:
            raise ValueError(
                f"can't use SQLAlchemy storage — already instantiated {type(self._storage).__name__}"
            )

        from suppgram.storages.sqlalchemy.models import Models
        from suppgram.storages.sqlalchemy.storage import SQLAlchemyStorage

        from sqlalchemy.ext.asyncio import create_async_engine

        self._sqlalchemy_engine = create_async_engine(sqlalchemy_uri)
        sqlalchemy_models = Models(engine=self._sqlalchemy_engine)
        self._storage = SQLAlchemyStorage(
            engine=self._sqlalchemy_engine,
            models=sqlalchemy_models,
        )
        return self

    def with_mongodb_storage(
        self, mongodb_uri: str, mongodb_database_name: Optional[str]
    ) -> "Builder":
        """Configure [MongoDBStorage][suppgram.storages.mongodb.MongoDBStorage]."""
        if self._storage is not None:
            raise ValueError(
                f"can't use MongoDB storage — already instantiated {type(self._storage).__name__}"
            )

        from motor.core import AgnosticDatabase
        from motor.motor_asyncio import AsyncIOMotorClient
        from suppgram.storages.mongodb.collections import Collections
        from suppgram.storages.mongodb.storage import MongoDBStorage

        self._mongodb_client = AsyncIOMotorClient(mongodb_uri, uuidRepresentation="standard")
        self._mongodb_database = cast(
            AgnosticDatabase,
            self._mongodb_client.get_default_database()
            if mongodb_database_name is None
            else self._mongodb_client.get_database(mongodb_database_name),
        )
        mongodb_collections = Collections(database=self._mongodb_database)
        self._storage = MongoDBStorage(collections=mongodb_collections)
        return self

    def with_texts(self, texts: TextProvider) -> "Builder":
        """Configure arbitrary [TextProvider][suppgram.texts.TextProvider] instance."""
        if self._texts is not None:
            raise ValueError(
                f"can't use {type(texts).__name__} — already instantiated {type(self._texts).__name__}"
            )

        self._texts = texts
        return self

    def with_texts_class_path(self, texts_class_path: str) -> "Builder":
        """Create [TextProvider][suppgram.texts.TextProvider] instance of given class.

        Assumes that its `__init__` method doesn't require any arguments."""
        if self._texts is not None:
            raise ValueError(
                f"can't use {texts_class_path} — already instantiated {type(self._texts).__name__}"
            )

        texts_module_name, texts_class_name = texts_class_path.rsplit(".", 1)
        texts_class = getattr(import_module(texts_module_name), texts_class_name)
        self._texts = texts_class()
        return self

    def with_telegram_manager_frontend(
        self, telegram_manager_bot_token: str, telegram_owner_id: Optional[int] = None
    ) -> "Builder":
        """
        Configure Telegram manager frontend.

        Arguments:
            telegram_manager_bot_token: Telegram bot token for manager bot
            telegram_owner_id: Telegram user ID of system administrator/owner
        """
        self._telegram_manager_bot_token = telegram_manager_bot_token
        self._telegram_owner_id = telegram_owner_id
        return self

    def with_telegram_customer_frontend(self, telegram_customer_bot_token: str) -> "Builder":
        """
        Configure Telegram customer frontend.

        Arguments:
            telegram_customer_bot_token: Telegram bot token for customer bot
        """
        self._telegram_customer_bot_token = telegram_customer_bot_token
        return self

    def with_shell_customer_frontend(self, uuid: Optional[UUID] = None) -> "Builder":
        """Configure shell customer frontend. Allows to chat with an agent directly in the shell.
        Useful for debug purposes."""
        if uuid is None:
            uuid = uuid4()
        self._shell_customer_uuid = uuid
        return self

    def with_pubnub_customer_frontend(
        self,
        pubnub_user_id: str,
        pubnub_channel_group: str,
        pubnub_message_converter_class_path: str = "suppgram.frontends.pubnub.DefaultMessageConverter",
    ) -> "Builder":
        """
        Configure PubNub customer frontend.

        Arguments:
            pubnub_user_id: PubNub user ID of the support user, on whose behalf agent messages will be sent to users
            pubnub_channel_group: ID of Pubnub channel group which includes all customers' chats with support
            pubnub_message_converter_class_path: allows to customize conversion between
                                                 Suppgram dataclasses and PubNub message JSONs
        """
        from suppgram.frontends.pubnub.configuration import make_pubnub_configuration
        from suppgram.frontends.pubnub.converter import make_pubnub_message_converter

        configuration = make_pubnub_configuration(pubnub_user_id)
        converter = make_pubnub_message_converter(pubnub_message_converter_class_path)

        self._pubnub_configuration = configuration
        self._pubnub_message_converter = converter
        self._pubnub_channel_group = pubnub_channel_group
        return self

    def with_telegram_agent_frontend(self, telegram_agent_bot_tokens: List[str]) -> "Builder":
        """
        Configure Telegram agent frontend.

        Arguments:
            telegram_agent_bot_tokens: list of Telegram bot tokens for agent bots. More tokens —
                                       more simultaneous chats with customers per agent
        """
        self._telegram_agent_bot_tokens = telegram_agent_bot_tokens
        return self

    def _build_storage(self) -> Storage:
        if self._storage is None:
            raise NoStorageSpecified()
        return self._storage

    def _build_texts(self) -> TextProvider:
        if self._texts is None:
            self._texts = EnglishTextProvider()
        return self._texts

    def _build_telegram_app_manager(self) -> Any:
        if self._telegram_app_manager is not None:
            return self._telegram_app_manager

        from suppgram.frontends.telegram.app_manager import TelegramAppManager

        tokens = [
            self._telegram_customer_bot_token,
            self._telegram_manager_bot_token,
            *self._telegram_agent_bot_tokens,
        ]
        self._telegram_app_manager = TelegramAppManager.from_tokens(tokens=[*filter(None, tokens)])
        return self._telegram_app_manager

    def _build_telegram_helper(self) -> Any:
        if self._telegram_helper is not None:
            return self._telegram_helper
        from suppgram.frontends.telegram.helper import TelegramHelper

        self._telegram_helper = TelegramHelper(
            manager_bot_token=self._telegram_manager_bot_token,
            app_manager=self._build_telegram_app_manager(),
            storage=self._build_telegram_storage(),
        )
        return self._telegram_helper

    def _build_telegram_storage(self) -> Any:
        if self._telegram_storage is not None:
            return self._telegram_storage
        self._build_storage()
        if self._sqlalchemy_engine is not None:
            from suppgram.bridges.sqlalchemy_telegram import SQLAlchemyTelegramBridge

            self._telegram_storage = SQLAlchemyTelegramBridge(self._sqlalchemy_engine)
        elif self._mongodb_database is not None:
            from suppgram.bridges.mongodb_telegram import MongoDBTelegramBridge

            self._telegram_storage = MongoDBTelegramBridge(self._mongodb_database)
        else:
            raise NoStorageSpecified()
        return self._telegram_storage

    def _build_workplace_managers(self) -> List[WorkplaceManager]:
        if self._workplace_managers:
            return self._workplace_managers
        if self._telegram_agent_bot_tokens:
            from suppgram.frontends.telegram.workplace_manager import (
                TelegramWorkplaceManager,
            )

            self._workplace_managers.append(
                TelegramWorkplaceManager(
                    self._telegram_agent_bot_tokens, self._build_telegram_app_manager()
                )
            )
        return self._workplace_managers

    def _build_backend(self) -> Backend:
        if self._backend is not None:
            return self._backend
        from suppgram.backends.local import LocalBackend

        self._backend = LocalBackend(
            storage=self._build_storage(),
            workplace_managers=self._build_workplace_managers(),
            texts=self._build_texts(),
        )
        return self._backend

    def _build_manager_frontend(self) -> Optional[ManagerFrontend]:
        if self._manager_frontend is not None:
            return self._manager_frontend

        if self._telegram_manager_bot_token:
            from suppgram.frontends.telegram.manager_frontend import (
                TelegramManagerFrontend,
            )

            self._manager_frontend = TelegramManagerFrontend(
                token=self._telegram_manager_bot_token,
                app_manager=self._build_telegram_app_manager(),
                backend=self._build_backend(),
                helper=self._build_telegram_helper(),
                storage=self._build_telegram_storage(),
                reporter=Reporter(self._build_storage()),
                texts=self._build_texts(),
            )

        return self._manager_frontend

    def _build_customer_frontends(self) -> List[CustomerFrontend]:
        if self._customer_frontends:
            return self._customer_frontends

        if self._telegram_customer_bot_token:
            from suppgram.frontends.telegram.customer_frontend import (
                TelegramCustomerFrontend,
            )

            logger.info("Initializing Telegram customer frontend")
            self._customer_frontends.append(
                TelegramCustomerFrontend(
                    token=self._telegram_customer_bot_token,
                    app_manager=self._build_telegram_app_manager(),
                    backend=self._build_backend(),
                    storage=self._build_telegram_storage(),
                    texts=self._build_texts(),
                )
            )

        if self._shell_customer_uuid:
            from suppgram.frontends.shell.customer_frontend import ShellCustomerFrontend

            logger.info("Initializing shell customer frontend")
            self._customer_frontends.append(
                ShellCustomerFrontend(backend=self._build_backend(), texts=self._build_texts())
            )

        if self._pubnub_configuration:
            from suppgram.frontends.pubnub.converter import MessageConverter
            from suppgram.frontends.pubnub.customer_frontend import (
                PubNubCustomerFrontend,
            )

            logger.info("Initializing PubNub customer frontend")

            self._customer_frontends.append(
                PubNubCustomerFrontend(
                    backend=self._build_backend(),
                    message_converter=cast(MessageConverter, self._pubnub_message_converter),
                    pubnub_channel_group=cast(str, self._pubnub_channel_group),
                    pubnub_configuration=self._pubnub_configuration,
                )
            )

        return self._customer_frontends

    def _build_agent_frontends(self) -> List[AgentFrontend]:
        if self._agent_frontends:
            return self._agent_frontends

        if self._telegram_agent_bot_tokens:
            from suppgram.frontends.telegram.agent_frontend import TelegramAgentFrontend

            self._agent_frontends.append(
                TelegramAgentFrontend(
                    agent_bot_tokens=self._telegram_agent_bot_tokens,
                    manager_bot_token=self._telegram_manager_bot_token,
                    app_manager=self._build_telegram_app_manager(),
                    backend=self._build_backend(),
                    helper=self._build_telegram_helper(),
                    storage=self._build_telegram_storage(),
                    texts=self._build_texts(),
                )
            )

        return self._agent_frontends

    async def _initialize(self):
        if self._initialized:
            return

        self.build()

        await self._storage.initialize()
        if self._telegram_storage:
            await self._telegram_storage.initialize()

        await flat_gather(runnable.initialize() for runnable in self._get_runnables())

        if self._telegram_owner_id:
            await self._backend.create_or_update_agent(
                AgentIdentification(telegram_user_id=self._telegram_owner_id)
            )

        self._initialized = True

    def _get_runnables(
        self,
    ) -> Iterable[Union[ManagerFrontend, CustomerFrontend, AgentFrontend]]:
        if manager_frontend := self._build_manager_frontend():
            yield manager_frontend
        yield from self._build_customer_frontends()
        yield from self._build_agent_frontends()
