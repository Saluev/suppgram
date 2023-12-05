from itertools import groupby
from typing import List, Iterable, Optional

from telegram import Update, BotCommand, User, Bot
from telegram.error import TelegramError
from telegram.ext import (
    MessageHandler,
    ContextTypes,
    CommandHandler,
    Application,
)
from telegram.ext.filters import TEXT, ChatType

from suppgram.backend import Backend
from suppgram.entities import (
    WorkplaceIdentification,
    MessageKind,
    Message,
    NewMessageForAgentEvent,
    AgentDiff,
)
from suppgram.errors import ConversationNotFound, AgentNotFound
from suppgram.frontend import (
    AgentFrontend,
)
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.frontends.telegram.helpers import send_text_answer
from suppgram.frontends.telegram.identification import (
    make_agent_identification,
    make_workplace_identification,
)
from suppgram.frontends.telegram.interfaces import (
    TelegramStorage,
    TelegramGroupRole,
    TelegramGroup,
)
from suppgram.helpers import flat_gather
from suppgram.texts.interface import TextsProvider


class TelegramAgentFrontend(AgentFrontend):
    _RESOLVE_COMMAND = "resolve"

    def __init__(
        self,
        agent_bot_tokens: List[str],
        manager_bot_token: Optional[str],
        app_manager: TelegramAppManager,
        backend: Backend,
        storage: TelegramStorage,
        texts: TextsProvider,
    ):
        self._backend = backend
        self._storage = storage
        self._texts = texts
        self._telegram_apps: List[Application] = []
        for token in agent_bot_tokens:
            app = app_manager.get_app(token)
            app.add_handlers(
                [
                    CommandHandler(
                        "start", self._handle_start_command, filters=ChatType.PRIVATE
                    ),
                    CommandHandler(
                        self._RESOLVE_COMMAND,
                        self._handle_resolve_command,
                        filters=ChatType.PRIVATE,
                    ),
                    MessageHandler(TEXT & ChatType.PRIVATE, self._handle_text_message),
                ]
            )
            self._telegram_apps.append(app)
        self._manager_bot: Optional[Bot] = (
            app_manager.get_app(manager_bot_token).bot if manager_bot_token else None
        )
        self._backend.on_new_message_for_agent.add_batch_handler(
            self._handle_new_message_for_agent_events
        )

    async def initialize(self):
        await super().initialize()
        await flat_gather(app.initialize() for app in self._telegram_apps)
        await flat_gather(
            app.bot.set_my_commands(
                [
                    BotCommand(
                        self._RESOLVE_COMMAND,
                        self._texts.telegram_resolve_command_description,
                    )
                ]
            )
            for app in self._telegram_apps
        )

    async def start(self):
        await flat_gather(app.updater.start_polling() for app in self._telegram_apps)
        await flat_gather(app.start() for app in self._telegram_apps)

    @send_text_answer
    async def _handle_start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> str:
        assert (
            update.effective_chat
        ), "command update with `ChatType.PRIVATE` filter should have `effective_chat`"
        assert (
            update.effective_user
        ), "command update with `ChatType.PRIVATE` filter should have `effective_user`"
        identification = make_agent_identification(update.effective_user)
        try:
            await self._backend.identify_agent(identification)
        except AgentNotFound:
            should_create = await self._check_belongs_to_agent_groups(
                update.effective_user
            )
            if not should_create:
                return self._texts.telegram_manager_permission_denied_message
            await self._backend.create_or_update_agent(
                identification,
                AgentDiff(
                    telegram_first_name=update.effective_user.first_name,
                    telegram_last_name=update.effective_user.last_name,
                    telegram_username=update.effective_user.username,
                ),
            )
        return self._texts.telegram_agent_start_message

    async def _check_belongs_to_agent_groups(self, user: User) -> bool:
        groups = await self._storage.get_groups_by_role(TelegramGroupRole.AGENTS)
        return any(
            await flat_gather(
                self._check_belongs_to_group(user, group) for group in groups
            )
        )

    async def _check_belongs_to_group(self, user: User, group: TelegramGroup) -> bool:
        if self._manager_bot is None:
            return False
        try:
            member = await self._manager_bot.get_chat_member(
                chat_id=group.telegram_chat_id, user_id=user.id
            )
            return member.status in (member.ADMINISTRATOR, member.OWNER, member.MEMBER)
        except TelegramError:  # TODO more precise exception handling
            return False

    async def _handle_resolve_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        assert (
            update.effective_chat
        ), "command update with `ChatType.PRIVATE` filter should have `effective_chat`"
        assert (
            update.effective_user
        ), "command update with `ChatType.PRIVATE` filter should have `effective_user`"
        try:
            agent = await self._backend.identify_agent(
                make_agent_identification(update.effective_user)
            )
        except AgentNotFound:
            answer = self._texts.telegram_manager_permission_denied_message
            await context.bot.send_message(update.effective_chat.id, answer)
            return

        try:
            conversation = await self._backend.identify_agent_conversation(
                make_workplace_identification(update, update.effective_user)
            )
        except ConversationNotFound:
            answer = self._texts.telegram_workplace_is_not_assigned_message
            await context.bot.send_message(update.effective_chat.id, answer)
            return

        await self._backend.resolve_conversation(agent, conversation)

    async def _handle_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        assert (
            update.effective_chat
        ), "update with `ChatType.PRIVATE` filter should have `effective_chat`"
        assert (
            update.effective_user
        ), "update with `ChatType.PRIVATE` filter should have `effective_user`"
        assert update.message, "update with `TEXT` filter should have `message`"
        try:
            conversation = await self._backend.identify_agent_conversation(
                WorkplaceIdentification(
                    telegram_user_id=update.effective_user.id,
                    telegram_bot_id=context.bot.bot.id,
                )
            )
        except ConversationNotFound:
            await context.bot.send_message(
                update.effective_chat.id,
                self._texts.telegram_workplace_is_not_assigned_message,
            )
            return
        await self._backend.process_message(
            conversation,
            Message(
                kind=MessageKind.FROM_AGENT,
                time_utc=update.message.date,  # TODO utc?
                text=update.message.text,
            ),
        )

    async def _handle_new_message_for_agent_events(
        self, events: List[NewMessageForAgentEvent]
    ):
        for _, batch_iter in groupby(
            events, lambda event: (event.workplace.agent.id, event.workplace.id)
        ):
            batch = list(batch_iter)
            workplace = batch[0].workplace
            if not workplace.telegram_bot_id:
                continue

            app = next(
                app
                for app in self._telegram_apps
                if app.bot.id == workplace.telegram_bot_id
            )
            texts = self._group_messages(event.message for event in batch)
            for text in texts:
                await app.bot.send_message(
                    chat_id=workplace.agent.telegram_user_id, text=text
                )

    def _group_messages(self, messages: Iterable[Message]) -> List[str]:
        # TODO actual grouping to reduce number of messages
        # TODO differentiation of previous agents' messages
        result: List[str] = []
        for message in messages:
            if message.text:
                result.append(message.text)
            elif message.kind == MessageKind.RESOLVED:
                result.append(self._texts.telegram_agent_conversation_resolved_message)
        return result
