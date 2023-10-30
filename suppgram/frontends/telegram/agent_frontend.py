import asyncio
from typing import List

from telegram import User, Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes
from telegram.ext.filters import TEXT, ChatType

from suppgram.errors import ConversationNotFound
from suppgram.interfaces import (
    AgentFrontend,
    Application,
)
from suppgram.entities import WorkplaceIdentification, MessageFrom, Message
from suppgram.texts.interface import Texts


class TelegramAgentFrontend(AgentFrontend):
    def __init__(self, tokens: List[str], backend: Application, texts: Texts):
        self._backend = backend
        self._texts = texts
        self._telegram_apps = []
        for token in tokens:
            app = ApplicationBuilder().token(token).build()
            app.add_handlers(
                [
                    MessageHandler(TEXT & ChatType.PRIVATE, self._handle_text_message),
                ]
            )
            self._telegram_apps.append(app)

    async def initialize(self):
        await super().initialize()
        await asyncio.gather(*(app.initialize() for app in self._telegram_apps))

    async def start(self):
        await asyncio.gather(
            *(app.updater.start_polling() for app in self._telegram_apps)
        )
        await asyncio.gather(*(app.start() for app in self._telegram_apps))

    async def _handle_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        try:
            conversation = await self._backend.identify_agent_conversation(
                WorkplaceIdentification(
                    telegram_user_id=update.effective_user.id,
                    telegram_bot_id=context.bot.bot.id,
                    telegram_chat_id=update.effective_chat.id,
                )
            )
        except ConversationNotFound:
            context.bot.send_message(
                update.effective_chat.id, self._texts.telegram_workplace_is_not_assigned
            )
            return
        await self._backend.process_message_from_agent(
            conversation, Message(from_=MessageFrom.AGENT, text=update.message.text)
        )
