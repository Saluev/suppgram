import asyncio
from itertools import groupby
from typing import List, Iterable, Optional

from telegram import Update, BotCommand, Bot, Chat
from telegram.error import TelegramError, BadRequest, Forbidden
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
    Workplace,
    ConversationEvent,
    Customer,
)
from suppgram.errors import ConversationNotFound, AgentNotFound
from suppgram.frontend import (
    AgentFrontend,
)
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.frontends.telegram.helpers import is_chat_not_found, is_blocked_by_user
from suppgram.frontends.telegram.identification import (
    make_agent_identification,
    make_workplace_identification,
    make_agent_diff,
)
from suppgram.frontends.telegram.interfaces import (
    TelegramStorage,
    TelegramGroupRole,
    TelegramGroup,
    TelegramMessageKind,
    TelegramMessage,
)
from suppgram.helpers import flat_gather
from suppgram.texts.interface import TextsProvider, Format


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
                    CommandHandler("start", self._handle_start_command, filters=ChatType.PRIVATE),
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
        self._backend.on_conversation_assignment.add_handler(self._handle_conversation_assignment)
        self._backend.on_new_message_for_agent.add_batch_handler(
            self._handle_new_message_for_agent_events
        )

    async def initialize(self):
        await super().initialize()
        await flat_gather(app.initialize() for app in self._telegram_apps)
        await flat_gather(self._set_commands(app) for app in self._telegram_apps)

    async def _set_commands(self, app: Application):
        resolve = BotCommand(
            self._RESOLVE_COMMAND,
            self._texts.telegram_resolve_command_description,
        )
        await app.bot.set_my_commands([resolve])

    async def start(self):
        await flat_gather(app.updater.start_polling() for app in self._telegram_apps)
        await flat_gather(app.start() for app in self._telegram_apps)

    async def _handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        assert update.effective_chat, "command update should have `effective_chat`"
        assert update.effective_user, "command update should have `effective_user`"
        workplace_identification = make_workplace_identification(update, update.effective_user)
        try:
            await self._backend.identify_workplace(workplace_identification)
        except AgentNotFound:
            should_create = await self._check_belongs_to_agent_groups(update.effective_user.id)
            if not should_create:
                await context.bot.send_message(
                    update.effective_chat.id,
                    self._texts.telegram_manager_permission_denied_message,
                )
                return
            agent_identification = workplace_identification.to_agent_identification()
            await self._backend.create_or_update_agent(
                agent_identification, make_agent_diff(update.effective_user)
            )

        await asyncio.gather(
            self._send_start_message_and_conversation_messages(
                update.effective_chat, workplace_identification, context
            ),
            self._delete_nudges(update),
        )

    async def _send_start_message_and_conversation_messages(
        self,
        effective_chat: Chat,
        workplace_identification: WorkplaceIdentification,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        await context.bot.send_message(effective_chat.id, self._texts.telegram_agent_start_message)

        try:
            conversation = await self._backend.identify_agent_conversation(workplace_identification)
        except ConversationNotFound:
            pass
        else:
            workplace = await self._backend.identify_workplace(workplace_identification)
            await self._send_new_messages(workplace, conversation.messages)

    async def _delete_nudges(self, update: Update):
        app = self._get_app_by_bot_id(update.get_bot().id)
        messages = await self._storage.get_messages(
            TelegramMessageKind.NUDGE_TO_START_BOT_NOTIFICATION,
            telegram_bot_username=app.bot.username,
        )
        await flat_gather(
            self._delete_message_if_exists(self._manager_bot, message) for message in messages
        )
        await self._storage.delete_messages(messages)

    async def _delete_message_if_exists(self, bot: Optional[Bot], message: TelegramMessage):
        if bot is None:
            return
        try:
            await bot.delete_message(
                chat_id=message.group.telegram_chat_id,
                message_id=message.telegram_message_id,
            )
        except TelegramError:  # TODO more precise exception handling
            pass

    async def _check_belongs_to_agent_groups(self, telegram_user_id: int) -> List[TelegramGroup]:
        groups = await self._storage.get_groups_by_role(TelegramGroupRole.AGENTS)
        return [
            group
            for group in await flat_gather(
                self._check_belongs_to_group(telegram_user_id, group) for group in groups
            )
            if group is not None
        ]

    async def _check_belongs_to_group(
        self, telegram_user_id: int, group: TelegramGroup
    ) -> Optional[TelegramGroup]:
        if self._manager_bot is None:
            return None
        try:
            member = await self._manager_bot.get_chat_member(
                chat_id=group.telegram_chat_id, user_id=telegram_user_id
            )
            return (
                group
                if member.status in (member.ADMINISTRATOR, member.OWNER, member.MEMBER)
                else None
            )
        except TelegramError:  # TODO more precise exception handling
            return None

    async def _handle_resolve_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        assert update.effective_chat, "command update should have `effective_chat`"
        assert update.effective_user, "command update should have `effective_user`"
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

    async def _handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        assert update.effective_chat, "message update should have `effective_chat`"
        assert update.effective_user, "message update should have `effective_user`"
        assert update.message, "message update should have `message`"
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

    async def _handle_conversation_assignment(self, event: ConversationEvent):
        conversation = event.conversation
        assert (
            conversation.assigned_workplace
        ), "conversation should have assigned workplace upon conversation assignment event"
        await self._send_customer_profile(conversation.assigned_workplace, conversation.customer)
        await self._send_new_messages(conversation.assigned_workplace, conversation.messages)

    async def _handle_new_message_for_agent_events(self, events: List[NewMessageForAgentEvent]):
        for _, batch_iter in groupby(
            events, lambda event: (event.workplace.agent.id, event.workplace.id)
        ):
            batch = list(batch_iter)
            workplace = batch[0].workplace
            messages = [event.message for event in batch]
            await self._send_new_messages(workplace, messages)

    async def _send_customer_profile(self, workplace: Workplace, customer: Customer):
        if workplace.telegram_user_id is None or workplace.telegram_bot_id is None:
            return
        app = self._get_app_by_bot_id(workplace.telegram_bot_id)
        profile = self._texts.compose_customer_profile(
            customer, Format.get_formats_supported_by_telegram()
        )
        await app.bot.send_message(
            chat_id=workplace.telegram_user_id, text=profile.text, parse_mode=profile.parse_mode
        )

    async def _send_new_messages(self, workplace: Workplace, messages: List[Message]):
        if workplace.telegram_user_id is None or workplace.telegram_bot_id is None:
            return

        app = self._get_app_by_bot_id(workplace.telegram_bot_id)
        texts = self._group_messages(messages)
        try:
            for text in texts:
                await app.bot.send_message(chat_id=workplace.telegram_user_id, text=text)
        except (BadRequest, Forbidden) as exc:
            if is_chat_not_found(exc) or is_blocked_by_user(exc):
                await self._nudge_to_start_bot(workplace)
                return
            raise

    def _get_app_by_bot_id(self, telegram_bot_id: int) -> Application:
        return next(app for app in self._telegram_apps if app.bot.id == telegram_bot_id)

    async def _nudge_to_start_bot(self, workplace: Workplace):
        assert workplace.telegram_user_id is not None, "should be called for Telegram workspaces"

        agent_groups = await self._check_belongs_to_agent_groups(workplace.telegram_user_id)
        await flat_gather(
            self._nudge_to_start_bot_in_group(workplace, group) for group in agent_groups
        )

    async def _nudge_to_start_bot_in_group(self, workplace: Workplace, group: TelegramGroup):
        assert workplace.telegram_bot_id is not None, "should be called for Telegram workspaces"
        if self._manager_bot is None:
            return
        app = self._get_app_by_bot_id(workplace.telegram_bot_id)
        bot_username = app.bot.username
        text = self._texts.compose_nudge_to_start_bot_notification(workplace.agent, bot_username)
        message = await self._manager_bot.send_message(
            chat_id=group.telegram_chat_id, text=text.text, parse_mode=text.parse_mode
        )
        await self._storage.insert_message(
            group,
            message.message_id,
            TelegramMessageKind.NUDGE_TO_START_BOT_NOTIFICATION,
            telegram_bot_username=bot_username,
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
