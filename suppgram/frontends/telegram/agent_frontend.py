from itertools import groupby
from typing import List, Iterable

from telegram import Update
from telegram.ext import (
    MessageHandler,
    ContextTypes,
    CommandHandler,
)
from telegram.ext.filters import TEXT, ChatType

from suppgram.entities import (
    WorkplaceIdentification,
    MessageFrom,
    Message,
    NewMessageForAgentEvent,
)
from suppgram.errors import ConversationNotFound, AgentNotFound
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.frontends.telegram.identification import make_agent_identification
from suppgram.helpers import flat_gather
from suppgram.interfaces import (
    AgentFrontend,
    Application,
    Permission,
)
from suppgram.texts.interface import Texts


class TelegramAgentFrontend(AgentFrontend):
    def __init__(
        self,
        tokens: List[str],
        app_manager: TelegramAppManager,
        backend: Application,
        texts: Texts,
    ):
        self._backend = backend
        self._texts = texts
        self._telegram_apps = []
        for token in tokens:
            app = app_manager.get_app(token)
            app.add_handlers(
                [
                    CommandHandler(
                        "start", self._handle_start_command, filters=ChatType.PRIVATE
                    ),
                    MessageHandler(TEXT & ChatType.PRIVATE, self._handle_text_message),
                ]
            )
            self._telegram_apps.append(app)
        self._backend.on_new_message_for_agent.add_batch_handler(
            self._handle_new_message_for_agent_events
        )

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

    async def _handle_new_message_for_agent_events(
        self, events: List[NewMessageForAgentEvent]
    ):
        for _, batch in groupby(
            events, lambda event: (event.agent.id, event.workplace.id)
        ):
            batch = list(batch)
            app = next(
                app
                for app in self._telegram_apps
                if app.bot.id == batch[0].workplace.telegram_bot_id
            )
            texts = self._group_messages(event.message for event in batch)
            for text in texts:
                await app.bot.send_message(
                    chat_id=batch[0].agent.telegram_user_id, text=text
                )

    def _group_messages(self, messages: Iterable[Message]) -> List[str]:
        # TODO actual grouping to reduce number of messages
        # TODO differentiation of previous agents' messages
        return [message.text for message in messages]
