import logging
from typing import cast, List

from telegram import Update, Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    BaseHandler,
)
from telegram.ext.filters import TEXT, ChatType, PHOTO

from suppgram.backend import Backend
from suppgram.entities import (
    MessageKind,
    Message,
    NewMessageForCustomerEvent,
    Conversation,
    ConversationEvent,
)
from suppgram.frontend import (
    CustomerFrontend,
)
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.frontends.telegram.callback_actions import CallbackActionKind
from suppgram.frontends.telegram.helpers import encode_callback_data, decode_callback_data
from suppgram.frontends.telegram.identification import (
    make_customer_identification,
    make_customer_diff,
)
from suppgram.frontends.telegram.storage import TelegramStorage, TelegramMessageKind
from suppgram.texts.interface import TextProvider

logger = logging.getLogger(__name__)


class TelegramCustomerFrontend(CustomerFrontend):
    """
    Allows customers to access the support system via Telegram bot.

    All messages from all users to a specific Telegram bot will be considered
    messages to the support. When agent responds, the bot will copy agent's
    message content and send it to the customer. Important: the message will be
    copied, not forwarded; thus the agent's identity will remain hidden.
    """

    def __init__(
        self,
        token: str,
        app_manager: TelegramAppManager,
        backend: Backend,
        storage: TelegramStorage,
        texts: TextProvider,
    ):
        """
        This constructor should not be used directly; use [Builder][suppgram.builder.Builder] instead.

        Arguments:
            token: Telegram bot token.
            app_manager: helper object storing built `telegram.ext.Application` instances.
            backend: used backend instance.
            storage: helper object encapsulating persistent storage of Telegram-specific data.
            texts: texts provider.
        """
        self._backend = backend
        self._texts = texts
        self._storage = storage
        self._telegram_app = app_manager.get_app(token)
        self._telegram_bot: Bot = self._telegram_app.bot
        self._telegram_app.add_handlers(self._make_handlers())
        self._backend.on_new_message_for_customer.add_handler(
            self._handle_new_message_for_customer_event
        )
        self._backend.on_conversation_rated.add_handler(self._handle_conversation_rated)

    def _make_handlers(self) -> List[BaseHandler]:
        return [
            CommandHandler("start", self._handle_start_command),
            CallbackQueryHandler(self._handle_callback_query),
            MessageHandler(ChatType.PRIVATE & (TEXT | PHOTO), self._handle_text_message),
            MessageHandler(ChatType.PRIVATE & ~(TEXT | PHOTO), self._handle_unsupported_message),
        ]

    async def initialize(self):
        await super().initialize()
        await self._telegram_app.initialize()

    async def start(self):
        await self._telegram_app.updater.start_polling()
        await self._telegram_app.start()

    async def _handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        assert update.effective_chat, "command update should have `effective_chat`"
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=self._texts.telegram_customer_start_message
        )

    async def _handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        assert update.callback_query, "callback query update should have `callback_query`"
        assert update.effective_chat, "callback query update should have `effective_chat`"
        assert update.effective_user, "callback query update should have `effective_user`"
        if not update.callback_query.data:
            # No idea how to handle this update.
            return
        callback_data = decode_callback_data(update.callback_query.data)
        action = callback_data["a"]
        conversation = await self._backend.identify_customer_conversation(
            make_customer_identification(update.effective_user)
        )
        conversation_to_rate = await self._backend.get_conversation(callback_data["c"])
        if action == CallbackActionKind.RATE:
            if conversation.customer.id != conversation_to_rate.customer.id:
                # Can't rate another person's conversation!
                # Probably someone's playing with the callback query payloads.
                return
            await self._backend.rate_conversation(conversation_to_rate, callback_data["r"])
        else:
            logger.info(f"Customer frontend received unsupported callback action {action!r}")

    async def _handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        assert update.message, "message update should have `message`"
        assert update.effective_user, "message update should have `effective_user`"
        identification = make_customer_identification(update.effective_user)
        await self._backend.create_or_update_customer(
            identification,
            make_customer_diff(update.effective_user),
        )
        conversation = await self._backend.identify_customer_conversation(identification)
        if update.message.photo:
            photo = max(update.message.photo, key=lambda p: p.width * p.height)
            file = await context.bot.get_file(photo.file_id)
            data = await file.download_as_bytearray()
            await self._backend.process_message(
                conversation,
                Message(
                    kind=MessageKind.FROM_CUSTOMER,
                    time_utc=update.message.date,
                    image=bytes(data),
                ),
            )
            if update.message.caption:
                await self._backend.process_message(
                    conversation,
                    Message(
                        kind=MessageKind.FROM_CUSTOMER,
                        time_utc=update.message.date,
                        text=update.message.caption,
                    ),
                )
        if update.message.text:
            await self._backend.process_message(
                conversation,
                Message(
                    kind=MessageKind.FROM_CUSTOMER,
                    time_utc=update.message.date,
                    text=update.message.text,
                ),
            )
        # TODO batch processing of multiple messages

    async def _handle_unsupported_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        assert update.message, "message update should have `message`"
        assert update.effective_chat, "message update should have `effective_chat`"
        await self._telegram_bot.send_message(
            chat_id=update.effective_chat.id,
            text=self._texts.telegram_customer_unsupported_message_content,
            reply_to_message_id=update.message.message_id,
        )

    async def _handle_new_message_for_customer_event(self, event: NewMessageForCustomerEvent):
        customer = event.conversation.customer
        if not customer.telegram_user_id:
            return

        if event.message.kind == MessageKind.RESOLVED:
            await self._handle_conversation_resolution(event)
            return

        if event.message.text:
            await self._telegram_bot.send_message(
                chat_id=customer.telegram_user_id,
                text=event.message.text,
            )

        if event.message.image:
            await self._telegram_bot.send_photo(
                chat_id=customer.telegram_user_id,
                photo=event.message.image,
            )

    async def _handle_conversation_resolution(self, event: NewMessageForCustomerEvent):
        customer = event.conversation.customer
        if customer.telegram_user_id is None:
            return

        reply_markup = InlineKeyboardMarkup(
            [
                [
                    self._make_rate_button(event.conversation, 1),
                    self._make_rate_button(event.conversation, 2),
                    self._make_rate_button(event.conversation, 3),
                ],
                [
                    self._make_rate_button(event.conversation, 4),
                    self._make_rate_button(event.conversation, 5),
                ],
            ]
        )
        message = await self._telegram_bot.send_message(
            chat_id=customer.telegram_user_id,
            text=self._texts.telegram_customer_conversation_resolved_message_placeholder,
        )
        group = await self._storage.create_or_update_chat(customer.telegram_user_id)
        await self._storage.insert_message(
            self._telegram_bot.id,
            group,
            message.message_id,
            TelegramMessageKind.RATE_CONVERSATION,
            conversation_id=event.conversation.id,
        )
        await self._telegram_bot.edit_message_text(
            chat_id=customer.telegram_user_id,
            message_id=message.message_id,
            text=self._texts.telegram_customer_conversation_resolved_message,
            reply_markup=reply_markup,
        )

    async def _handle_conversation_rated(self, event: ConversationEvent):
        messages = await self._storage.get_messages(
            TelegramMessageKind.RATE_CONVERSATION, conversation_id=event.conversation.id
        )
        for message in messages:
            # Normally just one message, so no `gather()`.
            await self._telegram_bot.edit_message_text(
                chat_id=message.chat.telegram_chat_id,
                message_id=message.telegram_message_id,
                text=self._texts.compose_customer_conversation_resolved_message(
                    cast(int, event.conversation.customer_rating)
                ),
                reply_markup=None,
            )

    def _make_rate_button(self, conversation: Conversation, rating: int) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            text=self._texts.format_rating(rating),
            callback_data=encode_callback_data(
                {"a": CallbackActionKind.RATE, "c": conversation.id, "r": rating}
            ),
        )
