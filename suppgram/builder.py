import logging
from importlib import import_module
from typing import Optional, List, Any, Iterable, cast
from uuid import UUID, uuid4

from suppgram.backend import WorkplaceManager, Backend
from suppgram.entities import AgentIdentification
from suppgram.frontend import ManagerFrontend, CustomerFrontend, AgentFrontend
from suppgram.helpers import flat_gather
from suppgram.permissions import PermissionChecker
from suppgram.storage import Storage
from suppgram.texts.en import EnglishTextsProvider
from suppgram.texts.interface import TextsProvider

logger = logging.getLogger(__name__)


class Builder:
    def __init__(self) -> None:
        # Implementation-specific objects are declared as `Any` to
        # avoid importing packages which may have missing dependencies.

        self._initialized = False

        self._storage: Optional[Storage] = None
        self._sqlalchemy_engine: Optional[Any] = None

        self._texts: Optional[TextsProvider] = None

        # Helper classes, including implementation-specific:
        self._telegram_app_manager: Optional[Any] = None
        self._telegram_storage: Optional[Any] = None
        self._pubnub_configuration: Optional[Any] = None
        self._pubnub_message_converter: Optional[Any] = None
        self._permission_checkers: List[PermissionChecker] = []
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

    async def start(self):
        await self._initialize()
        await flat_gather(runnable.start() for runnable in self._get_runnables())

    def with_storage(self, storage: Storage) -> "Builder":
        if self._storage is not None:
            raise ValueError(
                f"can't use {type(storage).__name__} — "
                f"already instantiated {type(self._storage).__name__}"
            )

        self._storage = storage
        return self

    def with_sqlalchemy_storage(self, sqlalchemy_url: str) -> "Builder":
        if self._storage is not None:
            raise ValueError(
                f"can't use SQLAlchemy storage — already instantiated {type(self._storage).__name__}"
            )

        from suppgram.storages.sqlalchemy import SQLAlchemyStorage

        from sqlalchemy.ext.asyncio import create_async_engine

        self._sqlalchemy_engine = create_async_engine(sqlalchemy_url)
        self._storage = SQLAlchemyStorage(self._sqlalchemy_engine)
        return self

    def with_texts(self, texts: TextsProvider) -> "Builder":
        if self._texts is not None:
            raise ValueError(
                f"can't use {type(texts).__name__} — already instantiated {type(self._texts).__name__}"
            )

        self._texts = texts
        return self

    def with_texts_class_path(self, texts_class_path: str) -> "Builder":
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
        self._telegram_manager_bot_token = telegram_manager_bot_token
        self._telegram_owner_id = telegram_owner_id
        return self

    def with_telegram_customer_frontend(
        self, telegram_customer_bot_token: str
    ) -> "Builder":
        self._telegram_customer_bot_token = telegram_customer_bot_token
        return self

    def with_shell_customer_frontend(self, uuid: Optional[UUID] = None) -> "Builder":
        if uuid is None:
            uuid = uuid4()
        self._shell_customer_uuid = uuid
        return self

    def with_pubnub_customer_frontend(
        self,
        pubnub_user_id: str,
        pubnub_channel_group: str,
        pubnub_message_converter_class_path: str,
    ) -> "Builder":
        from suppgram.frontends.pubnub.configuration import make_pubnub_configuration
        from suppgram.frontends.pubnub.converter import make_pubnub_message_converter

        configuration = make_pubnub_configuration(pubnub_user_id)
        converter = make_pubnub_message_converter(pubnub_message_converter_class_path)

        self._pubnub_configuration = configuration
        self._pubnub_message_converter = converter
        self._pubnub_channel_group = pubnub_channel_group
        return self

    def with_telegram_agent_frontend(
        self, telegram_agent_bot_tokens: List[str]
    ) -> "Builder":
        self._telegram_agent_bot_tokens = telegram_agent_bot_tokens
        return self

    def _build_storage(self) -> Storage:
        if self._storage is None:
            raise ValueError("no storage specified")
        return self._storage

    def _build_texts(self) -> TextsProvider:
        if self._texts is None:
            self._texts = EnglishTextsProvider()
        return self._texts

    def _build_telegram_app_manager(self) -> Any:
        if self._telegram_app_manager is not None:
            return self._telegram_app_manager

        from suppgram.frontends.telegram.app_manager import TelegramAppManager

        self._telegram_app_manager = TelegramAppManager(
            tokens=list(
                filter(
                    None,
                    [
                        self._telegram_customer_bot_token,
                        self._telegram_manager_bot_token,
                    ]
                    + list(self._telegram_agent_bot_tokens),
                )
            )
        )
        return self._telegram_app_manager

    def _build_telegram_storage(self) -> Any:
        if self._telegram_storage is not None:
            return self._telegram_storage
        self._build_storage()
        if self._sqlalchemy_engine:
            from suppgram.bridges.sqlalchemy_telegram import SQLAlchemyTelegramBridge

            self._telegram_storage = SQLAlchemyTelegramBridge(self._sqlalchemy_engine)
        else:
            raise ValueError("no storage specified")
        return self._telegram_storage

    def _build_permission_checkers(self) -> List[PermissionChecker]:
        if self._permission_checkers:
            return self._permission_checkers
        if self._telegram_owner_id:
            from suppgram.frontends.telegram.permission_checkers import (
                TelegramOwnerIDPermissionChecker,
            )

            self._permission_checkers.append(
                TelegramOwnerIDPermissionChecker(self._telegram_owner_id)
            )
        return self._permission_checkers

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
            permission_checkers=self._build_permission_checkers(),
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
                storage=self._build_telegram_storage(),
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
                ShellCustomerFrontend(
                    backend=self._build_backend(), texts=self._build_texts()
                )
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
                    message_converter=cast(
                        MessageConverter, self._pubnub_message_converter
                    ),
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
                    storage=self._build_telegram_storage(),
                    texts=self._build_texts(),
                )
            )

        return self._agent_frontends

    def _build(self):
        self._build_backend()
        self._build_manager_frontend()
        self._build_customer_frontends()
        self._build_agent_frontends()

    async def _initialize(self):
        if self._initialized:
            return

        self._build()

        await self._storage.initialize()
        if self._telegram_storage:
            await self._telegram_storage.initialize()

        if self._telegram_owner_id:
            await self._backend.create_agent(  # TODO upsert
                AgentIdentification(telegram_user_id=self._telegram_owner_id)
            )

        await flat_gather(runnable.initialize() for runnable in self._get_runnables())
        self._initialized = True

    def _get_runnables(
        self,
    ) -> Iterable[ManagerFrontend | CustomerFrontend | AgentFrontend]:
        if manager_frontend := self._build_manager_frontend():
            yield manager_frontend
        yield from self._build_customer_frontends()
        yield from self._build_agent_frontends()
