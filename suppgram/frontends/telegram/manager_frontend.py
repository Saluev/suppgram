import json
from enum import Enum

from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
)

from suppgram.frontends.telegram.identification import make_workplace_identification
from suppgram.frontends.telegram.interfaces import (
    TelegramStorage,
    TelegramGroupRole,
    TelegramMessageKind,
)
from suppgram.interfaces import (
    Application,
    ManagerFrontend,
)
from suppgram.entities import NewConversationEvent
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

        backend.on_new_conversation.add_handler(self._handle_new_conversation)
        self._telegram_app.add_handler(
            CallbackQueryHandler(self._handle_callback_query)
        )

    async def initialize(self):
        await super().initialize()
        await self._telegram_app.initialize()

    async def start(self):
        await self._telegram_app.updater.start_polling()
        await self._telegram_app.start()

    async def _handle_new_conversation(self, event: NewConversationEvent):
        conversation = event.conversation
        group = await self._storage.get_group_by_role(
            TelegramGroupRole.NEW_CONVERSATION_NOTIFICATIONS
        )
        message = await self._telegram_bot.send_message(
            group.telegram_chat_id,
            self._texts.telegram_new_conversation_notification_placeholder,
        )
        await self._storage.insert_message(
            group,
            message.message_id,
            TelegramMessageKind.NEW_CONVERSATION_NOTIFICATION,
            conversation_id=conversation.id,
        )
        text = self._texts.compose_telegram_new_conversation_notification(conversation)
        await self._telegram_bot.edit_message_text(
            text, group.telegram_chat_id, message.message_id
        )
        assign_to_me_button = InlineKeyboardButton(
            self._texts.telegram_assign_to_me_button,
            callback_data={
                "action": CallbackActionKind.ASSIGN_TO_ME,
                "conversation_id": conversation.id,
            },
        )
        await self._telegram_bot.edit_message_reply_markup(
            group.telegram_chat_id,
            message.message_id,
            reply_markup=InlineKeyboardMarkup([[assign_to_me_button]]),
        )

    async def _handle_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
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
        else:
            ...  # TODO logging
