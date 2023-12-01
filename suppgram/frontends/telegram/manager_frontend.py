import asyncio
import json
import logging
from enum import Enum
from typing import Optional, Any, List, Iterable

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
)
from telegram.ext.filters import ChatType, TEXT

from suppgram.backend import Backend
from suppgram.entities import (
    Conversation,
    NewUnassignedMessageFromCustomerEvent,
    AgentDiff,
    ConversationEvent,
    ConversationState,
    ConversationTag,
    ConversationTagEvent,
)
from suppgram.errors import AgentNotFound, PermissionDenied
from suppgram.frontend import (
    ManagerFrontend,
)
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.frontends.telegram.helpers import (
    send_text_answers,
    send_text_answer,
    arrange_buttons,
)
from suppgram.frontends.telegram.identification import (
    make_workplace_identification,
    make_agent_identification,
)
from suppgram.frontends.telegram.interfaces import (
    TelegramStorage,
    TelegramGroupRole,
    TelegramMessageKind,
    TelegramGroup,
    TelegramMessage,
)
from suppgram.helpers import flat_gather
from suppgram.permissions import Permission
from suppgram.texts.interface import TextsProvider

logger = logging.getLogger(__name__)


class CallbackActionKind(str, Enum):
    ASSIGN_TO_ME = "assign_to_me"
    ADD_CONVERSATION_TAG = "add_tag"
    REMOVE_CONVERSATION_TAG = "remove_tag"


class TelegramManagerFrontend(ManagerFrontend):
    _SEND_NEW_CONVERSATIONS_COMMAND = "send_new_conversations"
    _CREATE_CONVERSATION_TAG_COMMAND = "create_tag"

    def __init__(
        self,
        token: str,
        app_manager: TelegramAppManager,
        backend: Backend,
        storage: TelegramStorage,
        texts: TextsProvider,
    ):
        self._backend = backend
        self._storage = storage
        self._texts = texts
        self._telegram_app = app_manager.get_app(token)
        self._telegram_bot: Bot = self._telegram_app.bot

        backend.on_new_conversation.add_handler(self._handle_new_conversation_event)
        backend.on_new_unassigned_message_from_customer.add_handler(
            self._handle_new_unassigned_message_from_customer_event
        )
        backend.on_conversation_assignment.add_handler(
            self._handle_conversation_assignment_event
        )
        backend.on_conversation_resolution.add_handler(
            self._handle_conversation_resolution_event
        )
        backend.on_conversation_tag_added.add_handler(
            self._handle_conversation_tags_event
        )
        backend.on_conversation_tag_removed.add_handler(
            self._handle_conversation_tags_event
        )
        self._telegram_app.add_handlers(
            [
                CallbackQueryHandler(self._handle_callback_query),
                CommandHandler(
                    "start", self._handle_start_command, filters=ChatType.PRIVATE
                ),
                CommandHandler(
                    self._SEND_NEW_CONVERSATIONS_COMMAND,
                    self._handle_send_new_conversations_command,
                    filters=ChatType.GROUP,
                ),
                CommandHandler(
                    self._CREATE_CONVERSATION_TAG_COMMAND,
                    self._handle_create_conversation_tag_command,
                    filters=TEXT & (ChatType.GROUP | ChatType.PRIVATE),
                ),
            ]
        )

    async def initialize(self):
        await super().initialize()
        await self._telegram_app.initialize()
        await self._telegram_bot.set_my_commands(
            [
                BotCommand(
                    self._SEND_NEW_CONVERSATIONS_COMMAND,
                    self._texts.telegram_send_new_conversations_command_description,
                ),
                BotCommand(
                    self._CREATE_CONVERSATION_TAG_COMMAND,
                    self._texts.telegram_create_tag_command_description,
                ),
            ]
        )

    async def start(self):
        await self._telegram_app.updater.start_polling()
        await self._telegram_app.start()

    async def _handle_new_conversation_event(self, event: ConversationEvent):
        await self._send_or_edit_new_conversation_notifications(event.conversation)

    async def _handle_new_unassigned_message_from_customer_event(
        self, event: NewUnassignedMessageFromCustomerEvent
    ):
        if len(event.conversation.messages) == 1:
            # Already handled in `_handle_new_conversation_event()`.
            return
        await self._send_or_edit_new_conversation_notifications(event.conversation)

    async def _handle_conversation_assignment_event(self, event: ConversationEvent):
        await self._send_or_edit_new_conversation_notifications(event.conversation)

    async def _handle_conversation_resolution_event(self, event: ConversationEvent):
        await self._send_or_edit_new_conversation_notifications(event.conversation)

    async def _handle_conversation_tags_event(self, event: ConversationTagEvent):
        await self._send_or_edit_new_conversation_notifications(event.conversation)

    async def _send_new_conversation_notification(
        self,
        group: TelegramGroup,
        conversation: Conversation,
        all_tags: List[ConversationTag],
    ):
        message = await self._send_placeholder_message(
            group,
            self._texts.telegram_new_conversation_notification_placeholder,
            TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION,
            conversation_id=conversation.id,
        )
        await self._update_new_conversation_notification(
            message, conversation, all_tags
        )

    async def _send_placeholder_message(
        self,
        group: TelegramGroup,
        text: str,
        kind: TelegramMessageKind,
        conversation_id: Optional[Any] = None,
    ) -> TelegramMessage:
        message = await self._telegram_bot.send_message(group.telegram_chat_id, text)
        return await self._storage.insert_message(
            group,
            message.message_id,
            kind,
            conversation_id=conversation_id,
        )

    async def _send_or_edit_new_conversation_notifications(
        self, conversation: Conversation
    ):
        # For this conversation, there are some notifications in some groups.
        #
        # In those groups where newer messages with non-NEW conversation
        # notifications are present, we should delete the old notification and
        # create a new one to avoid losing the notification in the chat history.
        #
        # In other groups (where the notification is still on top or at least
        # among other NEW notifications), we should update the existing notification.
        messages = await self._storage.get_messages(
            TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION,
            conversation_id=conversation.id,
        )
        groups = await self._storage.get_groups_by_role(
            TelegramGroupRole.NEW_CONVERSATION_NOTIFICATIONS
        )
        group_ids = {group.telegram_chat_id for group in groups}
        newer_messages = await self._storage.get_newer_messages_of_kind(messages)
        newer_message_conversation_ids = {
            message.conversation_id for message in newer_messages
        }
        conversations = await self._backend.get_conversations(
            list(newer_message_conversation_ids)
        )
        not_new_conversation_ids = {
            conv.id for conv in conversations if conv.state != ConversationState.NEW
        }
        now_new_group_ids = [
            message.group.telegram_chat_id
            for message in newer_messages
            if message.conversation_id in not_new_conversation_ids
        ]

        messages_to_delete: List[TelegramMessage] = []
        messages_to_update: List[TelegramMessage] = []
        for message in messages:
            if message.group.telegram_chat_id in now_new_group_ids:
                messages_to_delete.append(message)
            else:
                messages_to_update.append(message)
                group_ids.remove(message.group.telegram_chat_id)

        groups_to_send_to = [
            group for group in groups if group.telegram_chat_id in group_ids
        ]

        all_tags = await self._backend.get_all_tags()

        await asyncio.gather(
            flat_gather(
                self._telegram_bot.delete_message(
                    chat_id=message.group.telegram_chat_id,
                    message_id=message.telegram_message_id,
                )
                for message in messages_to_delete
            ),
            flat_gather(
                self._send_new_conversation_notification(group, conversation, all_tags)
                for group in groups_to_send_to
            ),
            flat_gather(
                self._update_new_conversation_notification(
                    message, conversation, all_tags
                )
                for message in messages_to_update
            ),
        )

    async def _update_new_conversation_notification(
        self,
        message: TelegramMessage,
        conversation: Conversation,
        all_tags: List[ConversationTag],
    ):
        text = self._texts.compose_telegram_new_conversation_notification(conversation)

        assign_to_me_button = InlineKeyboardButton(
            self._texts.telegram_assign_to_me_button_text,
            callback_data=json.dumps(
                {
                    "a": CallbackActionKind.ASSIGN_TO_ME,
                    "c": conversation.id,
                },
                separators=(",", ":"),
            ),  # TODO encrypt
        )
        present_tag_ids = {tag.id for tag in conversation.tags}

        tag_buttons = [
            InlineKeyboardButton(
                self._texts.compose_remove_tag_button_text(tag)
                if tag.id in present_tag_ids
                else self._texts.compose_add_tag_button_text(tag),
                callback_data=json.dumps(
                    {
                        "a": CallbackActionKind.REMOVE_CONVERSATION_TAG
                        if tag.id in present_tag_ids
                        else CallbackActionKind.ADD_CONVERSATION_TAG,
                        "c": conversation.id,
                        "t": tag.id,
                    },
                    separators=(",", ":"),
                ),
            )
            for tag in all_tags
        ]

        inline_buttons = (
            [[assign_to_me_button]]
            if conversation.state == ConversationState.NEW
            else []
        )
        inline_buttons.extend(arrange_buttons(tag_buttons))

        try:
            await self._telegram_bot.edit_message_text(
                text.text,
                message.group.telegram_chat_id,
                message.telegram_message_id,
                parse_mode=text.parse_mode,
                reply_markup=InlineKeyboardMarkup(inline_buttons)
                if inline_buttons
                else None,
            )
        except BadRequest as exc:
            if "Message is not modified" not in str(exc):
                raise

    async def _handle_start_command(
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
        else:
            if self._backend.check_permission(agent, Permission.MANAGE):
                answer = self._texts.telegram_manager_start_message
            else:
                answer = self._texts.telegram_manager_permission_denied_message
        await context.bot.send_message(update.effective_chat.id, answer)

    @send_text_answer
    async def _handle_create_conversation_tag_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> Iterable[str]:
        assert update.message, "command update with `TEXT` filter should have `message`"
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

        existing_tags = await self._backend.get_all_tags()
        if any(tag.name == tag_name for tag in existing_tags):
            return self._texts.telegram_tag_already_exists_message

        try:
            await self._backend.create_tag(tag_name, agent)
            return self._texts.telegram_tag_successfully_created_message
        except PermissionDenied:
            return self._texts.telegram_create_tag_permission_denied_message

    async def _handle_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        assert (
            update.callback_query
        ), "callback query update should have `callback_query`"
        # TODO should it have effective chat?..
        assert (
            update.effective_user
        ), "callback query update should have `effective_user`"
        if not update.callback_query.data:
            # No idea how to handle this update.
            return
        await self._create_or_update_agent(update.effective_chat, update.effective_user)
        callback_data = json.loads(update.callback_query.data)
        action = callback_data["a"]
        if action == CallbackActionKind.ASSIGN_TO_ME:
            conversation_id = callback_data["c"]
            workplace = await self._backend.identify_workplace(
                make_workplace_identification(update, update.effective_user)
            )
            await self._backend.assign_agent(
                workplace.agent,
                workplace.agent,
                conversation_id,
            )
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
            logger.info(
                f"Manager frontend received unsupported callback action {action!r}"
            )

    async def _create_or_update_agent(self, effective_chat: Chat, effective_user: User):
        identification = make_agent_identification(effective_user)
        try:
            agent = await self._backend.identify_agent(identification)
        except AgentNotFound:
            group = await self._storage.get_group(effective_chat.id)
            if TelegramGroupRole.AGENTS not in group.roles:
                return
            agent = await self._backend.create_agent(identification)
        await self._backend.update_agent(
            agent.identification,
            AgentDiff(
                telegram_first_name=effective_user.first_name,
                telegram_last_name=effective_user.last_name,
                telegram_username=effective_user.username,
            ),
        )

    async def _handle_send_new_conversations_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        assert (
            update.effective_chat
        ), "command update with `ChatType.GROUP` filter should have `effective_chat`"
        assert (
            update.effective_user
        ), "command update with `ChatType.GROUP` filter should have `effective_user`"
        workplace = await self._backend.identify_workplace(
            make_workplace_identification(update, update.effective_user)
        )
        if not self._backend.check_permission(
            workplace.agent, Permission.TELEGRAM_ADD_GROUP_ROLE
        ):
            return  # TODO negative answer
        await self._storage.upsert_group(update.effective_chat.id)
        await self._storage.add_group_role(
            update.effective_chat.id, TelegramGroupRole.NEW_CONVERSATION_NOTIFICATIONS
        )
        # TODO positive answer
