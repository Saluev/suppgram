from telegram import Update, Bot
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
)
from telegram.ext.filters import TEXT, ChatType

from suppgram.interfaces import (
    UserFrontend,
    Application,
)
from suppgram.entities import (
    UserIdentification,
    MessageFrom,
    Message,
    NewMessageForUserEvent,
)
from suppgram.texts.interface import Texts


class TelegramUserFrontend(UserFrontend):
    def __init__(self, token: str, backend: Application, texts: Texts):
        self._backend = backend
        self._texts = texts
        self._telegram_app = ApplicationBuilder().token(token).build()
        self._telegram_bot: Bot = self._telegram_app.bot
        self._telegram_app.add_handlers(
            [
                CommandHandler("start", self._handle_start_command),
                MessageHandler(TEXT & ChatType.PRIVATE, self._handle_text_message),
            ]
        )
        self._backend.on_new_message_for_user.add_handler(
            self._handle_new_message_for_user_event
        )

    async def initialize(self):
        await super().initialize()
        await self._telegram_app.initialize()

    async def start(self):
        await self._telegram_app.updater.start_polling()
        await self._telegram_app.start()

    async def _handle_start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        await context.bot.send_message(
            update.effective_chat.id, self._texts.telegram_customer_start_message
        )

    async def _handle_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        conversation = await self._backend.identify_user_conversation(
            UserIdentification(telegram_user_id=update.effective_user.id)
        )
        await self._backend.process_message_from_user(
            conversation, Message(from_=MessageFrom.USER, text=update.message.text)
        )

    async def _handle_new_message_for_user_event(self, event: NewMessageForUserEvent):
        await self._telegram_bot.send_message(
            chat_id=event.user.telegram_user_id, text=event.message.text
        )