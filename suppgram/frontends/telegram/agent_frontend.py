import asyncio
import json
import logging
from itertools import groupby
from typing import List, Iterable, Optional, Callable, Awaitable, Mapping

from telegram import (
    Update,
    BotCommand,
    Bot,
    Chat,
)
from telegram.error import BadRequest, Forbidden
from telegram.ext import (
    MessageHandler,
    ContextTypes,
    CommandHandler,
    Application,
    CallbackQueryHandler,
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
    FINAL_STATES,
    Agent,
    Conversation,
)
from suppgram.errors import ConversationNotFound, AgentNotFound
from suppgram.frontend import (
    AgentFrontend,
)
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.frontends.telegram.callback_actions import CallbackActionKind
from suppgram.frontends.telegram.helper import TelegramHelper
from suppgram.frontends.telegram.helpers import (
    is_chat_not_found,
    is_blocked_by_user,
    make_pagination_keyboard,
    paginate_texts,
)
from suppgram.frontends.telegram.identification import (
    make_agent_identification,
    make_workplace_identification,
    make_agent_diff,
)
from suppgram.frontends.telegram.interfaces import (
    TelegramStorage,
    TelegramGroup,
    TelegramMessageKind,
    TelegramMessage,
)
from suppgram.helpers import flat_gather
from suppgram.texts.interface import TextsProvider, Format

logger = logging.getLogger(__name__)


class TelegramAgentFrontend(AgentFrontend):
    _POSTPONE_COMMAND = "postpone"
    _RESOLVE_COMMAND = "resolve"

    def __init__(
        self,
        agent_bot_tokens: List[str],
        manager_bot_token: Optional[str],
        app_manager: TelegramAppManager,
        backend: Backend,
        helper: TelegramHelper,
        storage: TelegramStorage,
        texts: TextsProvider,
    ):
        self._backend = backend
        self._helper = helper
        self._storage = storage
        self._texts = texts
        self._telegram_apps: List[Application] = []
        for token in agent_bot_tokens:
            app = app_manager.get_app(token)
            app.add_handlers(
                [
                    CommandHandler("start", self._handle_start_command, filters=ChatType.PRIVATE),
                    CommandHandler(
                        self._POSTPONE_COMMAND,
                        self._handle_postpone_command,
                        filters=ChatType.PRIVATE,
                    ),
                    CommandHandler(
                        self._RESOLVE_COMMAND,
                        self._handle_resolve_command,
                        filters=ChatType.PRIVATE,
                    ),
                    MessageHandler(TEXT & ChatType.PRIVATE, self._handle_text_message),
                    CallbackQueryHandler(self._handle_callback_query),
                ]
            )
            self._telegram_apps.append(app)
        self._telegram_app_by_bot_id: Mapping[int, Application] = {}
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
        postpone = BotCommand(
            self._POSTPONE_COMMAND,
            self._texts.telegram_postpone_command_description,
        )
        resolve = BotCommand(
            self._RESOLVE_COMMAND,
            self._texts.telegram_resolve_command_description,
        )
        await app.bot.set_my_commands([postpone, resolve])

    async def start(self):
        await flat_gather(app.updater.start_polling() for app in self._telegram_apps)
        await flat_gather(app.start() for app in self._telegram_apps)

    async def _handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        assert update.effective_chat, "command update should have `effective_chat`"
        assert update.effective_user, "command update should have `effective_user`"
        workplace_identification = make_workplace_identification(update, update.effective_user)
        try:
            workplace = await self._backend.identify_workplace(workplace_identification)
            agent = workplace.agent
        except AgentNotFound:
            should_create = await self._helper.check_belongs_to_agent_groups(
                update.effective_user.id
            )
            if not should_create:
                await context.bot.send_message(
                    update.effective_chat.id,
                    self._texts.telegram_manager_permission_denied_message,
                )
                return
            agent_identification = workplace_identification.to_agent_identification()
            agent = await self._backend.create_or_update_agent(
                agent_identification, make_agent_diff(update.effective_user)
            )

        await asyncio.gather(
            self._send_start_message_and_conversation_messages(
                update.effective_chat, workplace_identification, context
            ),
            self._delete_nudges(agent, update),
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
            await self._handle_conversation_assignment(ConversationEvent(conversation))

    async def _delete_nudges(self, agent: Agent, update: Update):
        app = self._get_app_by_bot_id(update.get_bot().id)
        messages = await self._storage.get_messages(
            TelegramMessageKind.NUDGE_TO_START_BOT_NOTIFICATION,
            agent_id=agent.id,
            telegram_bot_username=app.bot.username,
        )
        await flat_gather(self._helper.delete_message_if_exists(message) for message in messages)
        await self._storage.delete_messages(messages)

    async def _handle_postpone_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_conversation_command(
            update, context, self._backend.postpone_conversation
        )

    async def _handle_resolve_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_conversation_command(update, context, self._backend.resolve_conversation)

    async def _handle_conversation_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        command: Callable[[Agent, Conversation], Awaitable[None]],
    ):
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

        await command(agent, conversation)

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
                time_utc=update.message.date,
                text=update.message.text,
            ),
        )

    async def _handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        assert update.callback_query, "callback query update should have `callback_query`"
        assert update.effective_chat, "callback query update should have `effective_chat`"
        assert update.effective_user, "callback query update should have `effective_user`"
        if not update.callback_query.data:
            # No idea how to handle this update.
            return
        callback_data = json.loads(update.callback_query.data)
        action = callback_data.get("a")
        if action is None:
            return
        if action == CallbackActionKind.PAGE:
            group = await self._storage.get_group(callback_data["c"])
            message = await self._storage.get_message(group, callback_data["m"])
            customer = await self._backend.create_or_update_customer(
                message.customer_identification,
            )
            await self._update_previous_conversations_message(customer, message, callback_data["p"])
        else:
            logger.info(f"Agent frontend received unsupported callback action {action!r}")

    async def _handle_conversation_assignment(self, event: ConversationEvent):
        conversation = event.conversation
        workplace = conversation.assigned_workplace
        assert (
            workplace
        ), "conversation should have assigned workplace upon conversation assignment event"
        try:
            await self._send_customer_profile(workplace, conversation.customer)
            await self._send_previous_conversations_message(workplace, conversation.customer)
            await self._send_new_messages(workplace, conversation.messages)
        except (BadRequest, Forbidden) as exc:
            if is_chat_not_found(exc) or is_blocked_by_user(exc):
                await self._nudge_to_start_bot(workplace)
                return
            raise

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

    async def _send_previous_conversations_message(self, workplace: Workplace, customer: Customer):
        if workplace.telegram_bot_id is None or workplace.telegram_user_id is None:
            return
        pages = await self._compose_previous_conversations_message_texts(customer)
        if not pages:
            return
        app = self._get_app_by_bot_id(workplace.telegram_bot_id)
        message = await app.bot.send_message(chat_id=workplace.telegram_user_id, text=pages[0])
        group = await self._storage.create_or_update_group(workplace.telegram_user_id)
        tmessage = await self._storage.insert_message(
            workplace.telegram_bot_id,
            group,
            message.message_id,
            TelegramMessageKind.CUSTOMER_MESSAGE_HISTORY,
            customer_id=customer.id,
        )
        if (keyboard := make_pagination_keyboard(tmessage, len(pages), 0)) is not None:
            await app.bot.edit_message_reply_markup(
                chat_id=message.chat_id, message_id=message.message_id, reply_markup=keyboard
            )

    async def _update_previous_conversations_message(
        self, customer: Customer, message: TelegramMessage, page_idx: int
    ):
        app = self._get_app_by_bot_id(message.telegram_bot_id)
        pages = await self._compose_previous_conversations_message_texts(customer)
        if not (0 <= page_idx < len(pages)):
            return
        keyboard = make_pagination_keyboard(message, len(pages), page_idx)
        await app.bot.edit_message_text(
            pages[page_idx],
            message.group.telegram_chat_id,
            message.telegram_message_id,
            reply_markup=keyboard,
        )

    async def _compose_previous_conversations_message_texts(self, customer: Customer) -> List[str]:
        conversations = await self._backend.get_customer_conversations(customer)
        previous_conversations = [conv for conv in conversations if conv.state in FINAL_STATES]
        messages = sorted(
            [message for conv in previous_conversations for message in conv.messages],
            key=lambda m: m.time_utc,
        )
        if not messages:
            return []
        formatted_messages = self._format_previous_messages(messages)
        pages = self._paginate_formatted_messages(formatted_messages)
        return list(pages)

    def _format_previous_messages(self, messages: Iterable[Message]) -> Iterable[str]:
        for message in messages:
            yield self._texts.format_history_message(message)

    def _paginate_formatted_messages(self, messages: Iterable[str]) -> Iterable[str]:
        yield from paginate_texts(
            prefix=self._texts.message_history_title,
            texts=messages,
            suffix="",
            delimiter="\n",
            max_page_lines=15,
            max_page_chars=1000,
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
        if not self._telegram_app_by_bot_id:
            self._telegram_app_by_bot_id = {app.bot.id: app for app in self._telegram_apps}
        return self._telegram_app_by_bot_id[telegram_bot_id]

    async def _nudge_to_start_bot(self, workplace: Workplace):
        assert workplace.telegram_user_id is not None, "should be called for Telegram workspaces"

        agent_groups = await self._helper.check_belongs_to_agent_groups(workplace.telegram_user_id)
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
            workplace.telegram_bot_id,
            group,
            message.message_id,
            TelegramMessageKind.NUDGE_TO_START_BOT_NOTIFICATION,
            telegram_bot_username=bot_username,
        )

    def _group_messages(self, messages: Iterable[Message]) -> List[str]:
        # TODO differentiation of previous agents' messages
        # TODO actual grouping to reduce number of messages
        result: List[str] = []
        for message in messages:
            if message.text:
                result.append(message.text)
            elif message.kind == MessageKind.RESOLVED:
                result.append(self._texts.telegram_agent_conversation_resolved_message)
        return result
