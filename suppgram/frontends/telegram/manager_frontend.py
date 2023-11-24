import json
from enum import Enum
from typing import Optional, Any

from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    CommandHandler,
)
from telegram.ext.filters import ChatType

from suppgram.entities import (
    NewConversationEvent,
    Conversation,
    NewUnassignedMessageFromUserEvent,
    AgentDiff,
    Agent,
)
from suppgram.errors import AgentNotFound
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
from suppgram.interfaces import (
    Application,
    ManagerFrontend,
    Permission,
)
from suppgram.texts.interface import Texts


class CallbackActionKind(str, Enum):
    ASSIGN_TO_ME = "assign_to_me"


class TelegramManagerFrontend(ManagerFrontend):
    def __init__(
        self, token: str, backend: Application, storage: TelegramStorage, texts: Texts
    ):
        self._backend = backend
        self._storage = storage
        self._texts = texts
        self._telegram_app = ApplicationBuilder().token(token).build()
        self._telegram_bot: Bot = self._telegram_app.bot

        backend.on_new_conversation.add_handler(self._handle_new_conversation_event)
        backend.on_new_unassigned_message_from_user.add_handler(
            self._handle_new_unassigned_message_from_user_event
        )
        self._telegram_app.add_handlers(
            [
                CallbackQueryHandler(self._handle_callback_query),
                CommandHandler(
                    "start", self._handle_start_command, filters=ChatType.PRIVATE
                ),
                CommandHandler(
                    "send_new_conversations",
                    self._handle_send_new_conversations_command,
                ),
            ]
        )

    async def initialize(self):
        await super().initialize()
        await self._telegram_app.initialize()

    async def start(self):
        await self._telegram_app.updater.start_polling()
        await self._telegram_app.start()

    async def _handle_new_conversation_event(self, event: NewConversationEvent):
        await self._send_new_conversation_notifications(event.conversation)

    async def _send_new_conversation_notifications(self, conversation: Conversation):
        groups = await self._storage.get_groups_by_role(
            TelegramGroupRole.NEW_CONVERSATION_NOTIFICATIONS
        )
        await flat_gather(
            self._send_new_conversation_notification(group, conversation)
            for group in groups
        )

    async def _send_new_conversation_notification(
        self, group: TelegramGroup, conversation: Conversation
    ):
        message = await self._send_placeholder_message(
            group,
            self._texts.telegram_new_conversation_notification_placeholder,
            TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION,
            conversation_id=conversation.id,
        )
        await self._update_new_conversation_notification(message, conversation)

    async def _handle_new_unassigned_message_from_user_event(
        self, event: NewUnassignedMessageFromUserEvent
    ):
        messages = await self._storage.get_messages(
            TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION,
            conversation_id=event.conversation.id,
        )
        if messages:
            await flat_gather(
                self._update_new_conversation_notification(message, event.conversation)
                for message in messages
            )
        else:
            await self._send_new_conversation_notifications(event.conversation)

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

    async def _update_new_conversation_notification(
        self, message: TelegramMessage, conversation: Conversation
    ):
        text = self._texts.compose_telegram_new_conversation_notification(conversation)
        await self._telegram_bot.edit_message_text(
            text, message.group.telegram_chat_id, message.telegram_message_id
        )
        assign_to_me_button = InlineKeyboardButton(
            self._texts.telegram_assign_to_me_button_text,
            callback_data=json.dumps(
                {
                    "action": CallbackActionKind.ASSIGN_TO_ME,
                    "conversation_id": conversation.id,
                }
            ),
        )
        await self._telegram_bot.edit_message_reply_markup(
            message.group.telegram_chat_id,
            message.telegram_message_id,
            reply_markup=InlineKeyboardMarkup([[assign_to_me_button]]),
        )

    async def _handle_start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        try:
            agent = await self._backend.identify_agent(
                make_agent_identification(update)
            )
        except AgentNotFound:
            answer = self._texts.telegram_manager_permission_denied_message
        else:
            if self._backend.check_permission(agent, Permission.MANAGE):
                answer = self._texts.telegram_manager_start_message
            else:
                answer = self._texts.telegram_manager_permission_denied_message
        await context.bot.send_message(update.effective_chat.id, answer)

    async def _handle_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        await self._create_or_update_agent(update)
        callback_data = json.loads(update.callback_query.data)
        action = callback_data["action"]
        if action == CallbackActionKind.ASSIGN_TO_ME:
            conversation_id = callback_data["conversation_id"]
            workplace = await self._backend.identify_workplace(
                make_workplace_identification(update)
            )
            await self._backend.assign_agent(
                workplace.agent,
                workplace.agent,
                conversation_id,
            )
            messages = await self._storage.get_messages(
                kind=TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION,
                conversation_id=conversation_id,
            )
            for message in messages:
                await self._telegram_bot.edit_message_reply_markup(
                    message.group.telegram_chat_id,
                    message.telegram_message_id,
                    reply_markup=None,
                )
        else:
            ...  # TODO logging

    async def _create_or_update_agent(self, update: Update):
        identification = make_agent_identification(update)
        try:
            agent = await self._backend.identify_agent(identification)
        except AgentNotFound:
            group = await self._storage.get_group(update.effective_chat.id)
            if TelegramGroupRole.AGENTS not in group.roles:
                return
            agent = await self._backend.create_agent(identification)
        await self._backend.update_agent(
            AgentDiff(
                id=agent.id,
                telegram_first_name=update.effective_user.first_name,
                telegram_last_name=update.effective_user.last_name,
                telegram_username=update.effective_user.username,
            )
        )

    async def _handle_send_new_conversations_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        workplace = await self._backend.identify_workplace(
            make_workplace_identification(update)
        )
        if not self._backend.check_permission(
            workplace.agent, Permission.TELEGRAM_GROUP_ROLE_ADD
        ):
            return  # TODO negative answer
        await self._storage.upsert_group(update.effective_chat.id)
        await self._storage.add_group_role(
            update.effective_chat.id, TelegramGroupRole.NEW_CONVERSATION_NOTIFICATIONS
        )
        # TODO positive answer
