import asyncio
import logging
from dataclasses import replace
from time import perf_counter
from typing import Optional, Any, List

from telegram import (
    Bot,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Update,
    BotCommand,
    User,
    Chat,
)
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    BaseHandler,
)
from telegram.ext.filters import ChatType, StatusUpdate

from suppgram.analytics import Reporter
from suppgram.backend import Backend
from suppgram.entities import (
    Conversation,
    NewUnassignedMessageFromCustomerEvent,
    ConversationEvent,
    ConversationState,
    Tag,
    ConversationTagEvent,
    TagEvent, AgentDiff,
)
from suppgram.errors import AgentNotFound, PermissionDenied, TagAlreadyExists
from suppgram.frontend import (
    ManagerFrontend,
)
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.frontends.telegram.callback_actions import CallbackActionKind
from suppgram.frontends.telegram.helper import TelegramHelper
from suppgram.frontends.telegram.helpers import (
    send_text_answer,
    arrange_buttons,
    encode_callback_data,
    decode_callback_data,
)
from suppgram.frontends.telegram.identification import (
    make_agent_identification,
    make_agent_diff,
)
from suppgram.frontends.telegram.storage import (
    TelegramStorage,
    TelegramChatRole,
    TelegramMessageKind,
    TelegramChat,
    TelegramMessage,
)
from suppgram.helpers import flat_gather
from suppgram.texts.interface import TextProvider

logger = logging.getLogger(__name__)


class TelegramManagerFrontend(ManagerFrontend):
    _SEND_NEW_CONVERSATIONS_COMMAND = "send_new_conversations"
    _AGENTS_COMMAND = "agents"
    _CREATE_CONVERSATION_TAG_COMMAND = "create_tag"
    _REPORT_COMMAND = "report"

    def __init__(
        self,
        token: str,
        app_manager: TelegramAppManager,
        backend: Backend,
        helper: TelegramHelper,
        reporter: Reporter,
        storage: TelegramStorage,
        texts: TextProvider,
    ) -> None:
        self._backend = backend
        self._helper = helper
        self._reporter = reporter
        self._storage = storage
        self._texts = texts
        self._telegram_app = app_manager.get_app(token)
        self._telegram_bot: Bot = self._telegram_app.bot

        backend.on_new_conversation.add_handler(self._handle_new_conversation_event)
        backend.on_new_unassigned_message_from_customer.add_handler(
            self._handle_new_unassigned_message_from_customer_event
        )
        backend.on_conversation_assignment.add_handler(self._handle_conversation_assignment_event)
        backend.on_conversation_resolution.add_handler(self._handle_conversation_resolution_event)
        backend.on_conversation_rated.add_handler(self._handle_conversation_rated_event)
        backend.on_conversation_tag_added.add_handler(self._handle_conversation_tags_event)
        backend.on_conversation_tag_removed.add_handler(self._handle_conversation_tags_event)
        backend.on_tag_created.add_handler(self._handle_tag_event)
        self._telegram_app.add_handlers(self._make_handlers())

    def _make_handlers(self) -> List[BaseHandler]:
        return [
            CallbackQueryHandler(self._handle_callback_query),
            CommandHandler("start", self._handle_start_command, filters=ChatType.PRIVATE),
            CommandHandler(
                self._AGENTS_COMMAND,
                self._handle_agents_command,
                filters=ChatType.GROUPS,
            ),
            CommandHandler(
                self._SEND_NEW_CONVERSATIONS_COMMAND,
                self._handle_send_new_conversations_command,
                filters=ChatType.GROUPS,
            ),
            CommandHandler(
                self._CREATE_CONVERSATION_TAG_COMMAND,
                self._handle_create_conversation_tag_command,
                filters=ChatType.GROUPS | ChatType.PRIVATE,
            ),
            CommandHandler(
                self._REPORT_COMMAND,
                self._handle_report_command,
                filters=ChatType.GROUPS | ChatType.PRIVATE,
            ),
            MessageHandler(StatusUpdate.NEW_CHAT_MEMBERS, self._handle_new_chat_members),
            MessageHandler(StatusUpdate.LEFT_CHAT_MEMBER, self._handle_left_chat_member),
        ]

    async def initialize(self) -> None:
        await super().initialize()
        await self._telegram_app.initialize()
        await self._set_commands()

    async def _set_commands(self) -> None:
        await self._telegram_bot.set_my_commands(
            [
                BotCommand(
                    self._AGENTS_COMMAND,
                    self._texts.telegram_agents_command_description,
                ),
                BotCommand(
                    self._SEND_NEW_CONVERSATIONS_COMMAND,
                    self._texts.telegram_send_new_conversations_command_description,
                ),
                BotCommand(
                    self._CREATE_CONVERSATION_TAG_COMMAND,
                    self._texts.telegram_create_tag_command_description,
                ),
                BotCommand(self._REPORT_COMMAND, self._texts.telegram_report_command_description),
            ]
        )

    async def start(self) -> None:
        assert self._telegram_app.updater
        await self._telegram_app.updater.start_polling()
        await self._telegram_app.start()

    async def _handle_new_conversation_event(self, event: ConversationEvent) -> None:
        await self._send_or_edit_new_conversation_notifications(event.conversation)

    async def _handle_new_unassigned_message_from_customer_event(
        self, event: NewUnassignedMessageFromCustomerEvent
    ) -> None:
        if len(event.conversation.messages) == 1:
            # Already handled in `_handle_new_conversation_event()`.
            return
        await self._send_or_edit_new_conversation_notifications(event.conversation)

    async def _handle_conversation_assignment_event(self, event: ConversationEvent) -> None:
        await self._send_or_edit_new_conversation_notifications(event.conversation)

    async def _handle_conversation_resolution_event(self, event: ConversationEvent) -> None:
        await self._send_or_edit_new_conversation_notifications(event.conversation)

    async def _handle_conversation_rated_event(self, event: ConversationEvent) -> None:
        await self._send_or_edit_new_conversation_notifications(event.conversation)

    async def _handle_conversation_tags_event(self, event: ConversationTagEvent) -> None:
        await self._send_or_edit_new_conversation_notifications(event.conversation)

    async def _handle_tag_event(self, _: TagEvent) -> None:
        # Refresh keyboards for all NEW conversations.
        messages = await self._storage.get_messages(
            kind=TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION
        )
        conversation_ids = list(
            {message.conversation_id for message in messages if message.conversation_id is not None}
        )
        conversations = await self._backend.get_conversations(conversation_ids)
        conv_by_id = {conv.id: conv for conv in conversations}
        all_tags = await self._backend.get_all_tags()
        await flat_gather(
            self._update_new_conversation_notification(message, conv, all_tags, keyboard_only=True)
            for message in messages
            for conv in (conv_by_id[message.conversation_id],)
            if conv.state == ConversationState.NEW
        )

    async def _send_new_conversation_notification(
        self,
        group: TelegramChat,
        conversation: Conversation,
        all_tags: List[Tag],
    ) -> None:
        message = await self._send_placeholder_message(
            group,
            self._texts.telegram_new_conversation_notification_placeholder,
            TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION,
            conversation_id=conversation.id,
        )
        await self._update_new_conversation_notification(message, conversation, all_tags)

    async def _send_placeholder_message(
        self,
        group: TelegramChat,
        text: str,
        kind: TelegramMessageKind,
        conversation_id: Optional[Any] = None,
    ) -> TelegramMessage:
        message = await self._telegram_bot.send_message(group.telegram_chat_id, text)
        return await self._storage.insert_message(
            self._telegram_bot.id,
            group,
            message.message_id,
            kind,
            conversation_id=conversation_id,
        )

    async def _send_or_edit_new_conversation_notifications(
        self, conversation: Conversation
    ) -> None:
        # For this conversation, there are some notifications in some chats.
        #
        # In those chats where newer messages with non-NEW conversation
        # notifications are present, we should delete the old notification and
        # create a new one to avoid losing the notification in the chat history.
        #
        # In other chats (where the notification is still on top or at least
        # among other NEW notifications), we should update the existing notification.
        #
        # First, fetch conversation WITH MESSAGES from the database.
        # (Events by default contain lightweight conversations without messages.)
        conversation = await self._backend.get_conversation(conversation.id)
        messages = await self._storage.get_messages(
            TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION,
            conversation_id=conversation.id,
        )
        chats = await self._storage.get_chats_by_role(
            TelegramChatRole.NEW_CONVERSATION_NOTIFICATIONS
        )
        group_ids = {group.telegram_chat_id for group in chats}
        newer_messages = await self._storage.get_newer_messages_of_kind(messages)
        newer_message_conversation_ids = {message.conversation_id for message in newer_messages}
        conversations = await self._backend.get_conversations(list(newer_message_conversation_ids))
        not_new_conversation_ids = {
            conv.id for conv in conversations if conv.state != ConversationState.NEW
        }
        now_new_group_ids = [
            message.chat.telegram_chat_id
            for message in newer_messages
            if message.conversation_id in not_new_conversation_ids
        ]

        messages_to_delete: List[TelegramMessage] = []
        messages_to_update: List[TelegramMessage] = []
        for message in messages:
            if message.chat.telegram_chat_id in now_new_group_ids:
                messages_to_delete.append(message)
            else:
                messages_to_update.append(message)
                group_ids.remove(message.chat.telegram_chat_id)

        chats_to_send_to = [group for group in chats if group.telegram_chat_id in group_ids]

        all_tags = await self._backend.get_all_tags()

        await asyncio.gather(
            flat_gather(
                self._telegram_bot.delete_message(
                    chat_id=message.chat.telegram_chat_id,
                    message_id=message.telegram_message_id,
                )
                for message in messages_to_delete
            ),
            flat_gather(
                self._send_new_conversation_notification(group, conversation, all_tags)
                for group in chats_to_send_to
            ),
            flat_gather(
                self._update_new_conversation_notification(message, conversation, all_tags)
                for message in messages_to_update
            ),
        )

    async def _update_new_conversation_notification(
        self,
        message: TelegramMessage,
        conversation: Conversation,
        all_tags: List[Tag],
        keyboard_only: bool = False,
    ) -> None:
        present_tag_ids = {tag.id for tag in conversation.tags}

        assign_buttons = (
            [[self._make_assign_to_me_button(conversation)]]
            if conversation.state == ConversationState.NEW
            else []
        )
        tag_buttons = [
            self._make_remove_tag_button(conversation, tag)
            if tag.id in present_tag_ids
            else self._make_add_tag_button(conversation, tag)
            for tag in all_tags
        ]
        inline_buttons = [*assign_buttons, *arrange_buttons(tag_buttons)]
        inline_keyboard = InlineKeyboardMarkup(inline_buttons) if inline_buttons else None

        if keyboard_only:
            try:
                await self._telegram_bot.edit_message_reply_markup(
                    message.chat.telegram_chat_id,
                    message.telegram_message_id,
                    reply_markup=inline_keyboard,
                )
                return
            except BadRequest as exc:
                if "Message is not modified" not in str(exc):
                    raise

        text = self._texts.compose_telegram_conversation_notification(conversation)
        try:
            await self._telegram_bot.edit_message_text(
                text.text,
                message.chat.telegram_chat_id,
                message.telegram_message_id,
                parse_mode=text.parse_mode,
                reply_markup=inline_keyboard,
            )
        except BadRequest as exc:
            if "Message is not modified" not in str(exc):
                raise

    def _make_assign_to_me_button(self, conversation: Conversation) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            self._texts.telegram_assign_to_me_button_text,
            callback_data=encode_callback_data(
                {"a": CallbackActionKind.ASSIGN_TO_ME, "c": conversation.id}
            ),
        )

    def _make_add_tag_button(self, conversation: Conversation, tag: Tag) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            text=self._texts.compose_add_tag_button_text(tag),
            callback_data=encode_callback_data(
                {"a": CallbackActionKind.ADD_CONVERSATION_TAG, "c": conversation.id, "t": tag.id}
            ),
        )

    def _make_remove_tag_button(self, conversation: Conversation, tag: Tag) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            text=self._texts.compose_remove_tag_button_text(tag),
            callback_data=encode_callback_data(
                {"a": CallbackActionKind.REMOVE_CONVERSATION_TAG, "c": conversation.id, "t": tag.id}
            ),
        )

    async def _handle_start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        assert (
            update.effective_chat
        ), "command update with `ChatType.PRIVATE` filter should have `effective_chat`"
        assert (
            update.effective_user
        ), "command update with `ChatType.PRIVATE` filter should have `effective_user`"
        try:
            await self._backend.identify_agent(make_agent_identification(update.effective_user))
        except AgentNotFound:
            answer = self._texts.telegram_manager_permission_denied_message
        else:
            answer = self._texts.telegram_manager_start_message
        await context.bot.send_message(update.effective_chat.id, answer)

    @send_text_answer
    async def _handle_create_conversation_tag_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> str:
        assert update.message, "command update with `TEXT` filter should have `message`"
        assert update.message.text, "command update with `TEXT` filter should have `message.text`"
        assert update.effective_user, "command update should have `effective_user`"
        try:
            agent = await self._backend.identify_agent(
                make_agent_identification(update.effective_user)
            )
        except AgentNotFound:
            return self._texts.telegram_manager_permission_denied_message

        tag_name = update.message.text.removeprefix(
            f"/{self._CREATE_CONVERSATION_TAG_COMMAND}"
        ).strip()
        if not tag_name:
            return self._texts.telegram_create_tag_usage_message

        try:
            await self._backend.create_tag(tag_name, agent)
            return self._texts.telegram_tag_successfully_created_message
        except TagAlreadyExists:
            return self._texts.telegram_tag_already_exists_message
        except PermissionDenied:
            return self._texts.telegram_create_tag_permission_denied_message

    async def _handle_report_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        assert update.message, "command update with `TEXT` filter should have `message`"
        assert update.message.text, "command update with `TEXT` filter should have `message.text`"
        assert update.effective_chat, "command update should have `effective_chat`"
        assert update.effective_user, "command update should have `effective_user`"

        chat_id = update.effective_chat.id

        try:
            await self._backend.identify_agent(make_agent_identification(update.effective_user))
        except AgentNotFound:
            await context.bot.send_message(
                chat_id=chat_id, text=self._texts.telegram_manager_permission_denied_message
            )

        last_progress = "0%"
        last_progress_update = perf_counter()
        message = await context.bot.send_message(
            chat_id=chat_id,
            text=self._texts.telegram_report_message_placeholder.format(progress=last_progress),
        )

        async def progress_callback(progress: float) -> None:
            nonlocal last_progress
            nonlocal last_progress_update
            now = perf_counter()
            curr_progress = f"{100.0 * progress:.1f}%"
            if now - last_progress_update > 1.0 and curr_progress != last_progress:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message.message_id,
                    text=self._texts.telegram_report_message_placeholder.format(
                        progress=curr_progress
                    ),
                )
                last_progress = curr_progress
                last_progress_update = now

        report = await self._reporter.report(progress_callback)
        await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        await context.bot.send_message(
            chat_id=chat_id, text=self._texts.telegram_report_message.format(report=report)
        )
        # TODO send xlsx report

    async def _handle_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        assert update.callback_query, "callback query update should have `callback_query`"
        assert update.effective_chat, "callback query update should have `effective_chat`"
        assert update.effective_user, "callback query update should have `effective_user`"
        if not update.callback_query.data:
            # No idea how to handle this update.
            logger.warning("Received callback query with no data")
            return
        await self._create_or_update_agent(update.effective_chat, update.effective_user)
        callback_data = decode_callback_data(update.callback_query.data)
        action = callback_data["a"]
        if action == CallbackActionKind.ASSIGN_TO_ME:
            conversation_id = callback_data["c"]
            agent = await self._backend.identify_agent(
                make_agent_identification(update.effective_user)
            )
            await self._backend.assign_agent(agent, agent, conversation_id)
        elif action in (
            CallbackActionKind.ADD_CONVERSATION_TAG,
            CallbackActionKind.REMOVE_CONVERSATION_TAG,
        ):
            conversation_id = callback_data["c"]
            conversation = await self._backend.get_conversation(conversation_id)
            all_tags = await self._backend.get_all_tags()
            tag_id = callback_data["t"]
            tag = next(tag for tag in all_tags if tag.id == tag_id)
            if action == CallbackActionKind.ADD_CONVERSATION_TAG:
                await self._backend.add_tag_to_conversation(conversation, tag)
            else:
                await self._backend.remove_tag_from_conversation(conversation, tag)
        else:
            logger.info(f"Manager frontend received unsupported callback action {action!r}")

    async def _create_or_update_agent(self, effective_chat: Chat, effective_user: User) -> None:
        identification = make_agent_identification(effective_user)
        diff = make_agent_diff(effective_user)
        group = await self._storage.get_chat(effective_chat.id)
        if TelegramChatRole.AGENTS in group.roles:
            # User clicked button in agent chat - so even if they left the chat
            # previously (and were deactivated), they are active agents now.
            diff = replace(diff, deactivated=False)
        try:
            await self._backend.update_agent(identification, diff)
        except AgentNotFound:
            if TelegramChatRole.AGENTS not in group.roles:
                return
            await self._backend.create_or_update_agent(identification, diff)

    async def _handle_agents_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        assert update.effective_chat, "command update should have `effective_chat`"
        assert update.effective_user, "command update should have `effective_user`"
        await self._backend.identify_agent(make_agent_identification(update.effective_user))
        await self._storage.create_or_update_chat(update.effective_chat.id)
        await self._storage.add_chat_roles(
            update.effective_chat.id,
            TelegramChatRole.AGENTS,
            TelegramChatRole.NEW_CONVERSATION_NOTIFICATIONS,
        )
        await context.bot.send_message(
            update.effective_chat.id, self._texts.telegram_agents_command_success_message
        )

    async def _handle_send_new_conversations_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        assert update.effective_chat, "command update should have `effective_chat`"
        assert update.effective_user, "command update should have `effective_user`"
        await self._backend.identify_agent(make_agent_identification(update.effective_user))
        await self._storage.create_or_update_chat(update.effective_chat.id)
        await self._storage.add_chat_roles(
            update.effective_chat.id, TelegramChatRole.NEW_CONVERSATION_NOTIFICATIONS
        )
        await context.bot.send_message(
            update.effective_chat.id,
            self._texts.telegram_send_new_conversations_command_success_message,
        )

    async def _handle_new_chat_members(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        assert (
            update.effective_chat
        ), "update with NEW_CHAT_MEMBERS filter should have `effective_chat`"
        assert (
            update.message and update.message.new_chat_members
        ), "update with NEW_CHAT_MEMBERS filter should have `message.new_chat_members`"
        group = await self._storage.create_or_update_chat(update.effective_chat.id)
        if TelegramChatRole.AGENTS not in group.roles:
            return
        await flat_gather(
            self._backend.create_or_update_agent(make_agent_identification(user), AgentDiff(deactivated=False))
            for user in update.message.new_chat_members
            if not user.is_bot
        )

    async def _handle_left_chat_member(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        assert (
            update.effective_chat
        ), "update with LEFT_CHAT_MEMBERS filter should have `effective_chat`"
        assert (
            update.message and update.message.left_chat_member
        ), "update with LEFT_CHAT_MEMBERS filter should have `message.left_chat_member`"

        user = update.message.left_chat_member
        if user.is_bot:
            return

        group = await self._storage.create_or_update_chat(update.effective_chat.id)
        if TelegramChatRole.AGENTS not in group.roles:
            return

        try:
            agent = await self._backend.identify_agent(make_agent_identification(user))
        except AgentNotFound:
            return

        if await self._helper.check_belongs_to_agent_chats(user.id):
            return

        await self._backend.deactivate_agent(agent)
