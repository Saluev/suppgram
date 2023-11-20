import asyncio
from typing import List

from telegram import User, Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    CommandHandler,
)
from telegram.ext.filters import TEXT, ChatType

from suppgram.errors import ConversationNotFound, AgentNotFound
from suppgram.frontends.telegram.identification import make_agent_identification
from suppgram.helpers import flat_gather
from suppgram.interfaces import (
    AgentFrontend,
    Application,
    Permission,
    Decision,
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
                    CommandHandler(
                        "start", self._handle_start_command, filters=ChatType.PRIVATE
                    ),
                    MessageHandler(TEXT & ChatType.PRIVATE, self._handle_text_message),
                ]
            )
            self._telegram_apps.append(app)

    async def initialize(self):
        await super().initialize()
        await flat_gather(app.initialize() for app in self._telegram_apps)

    async def start(self):
        await flat_gather(app.updater.start_polling() for app in self._telegram_apps)
        await flat_gather(app.start() for app in self._telegram_apps)

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
            if self._backend.check_permission(agent, Permission.SUPPORT):
                answer = self._texts.telegram_agent_start_message
            else:
                answer = self._texts.telegram_agent_permission_denied_message
        await context.bot.send_message(update.effective_chat.id, answer)

    async def _handle_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        try:
            conversation = await self._backend.identify_agent_conversation(
                WorkplaceIdentification(
                    telegram_user_id=update.effective_user.id,
                    telegram_bot_id=context.bot.bot.id,
                )
            )
        except ConversationNotFound:
            context.bot.send_message(
                update.effective_chat.id,
                self._texts.telegram_workplace_is_not_assigned_message,
            )
            return
        await self._backend.process_message_from_agent(
            conversation, Message(from_=MessageFrom.AGENT, text=update.message.text)
        )
