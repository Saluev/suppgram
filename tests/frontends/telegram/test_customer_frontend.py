from datetime import datetime, timezone
from unittest import mock

import pytest
from telegram import InlineKeyboardMarkup, Sticker

from suppgram.entities import (
    CustomerIdentification,
    ConversationState,
    MessageKind,
    NewMessageForCustomerEvent,
    Message,
)

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_customer_start(storage, telegram_update, send_message_mock):
    update = await telegram_update(from_customer=True, text="/start")
    send_message_mock.assert_called_once_with(
        chat_id=update.effective_chat.id,
        text="👋 Welcome to support service! Please describe your problem.",
    )


@pytest.mark.asyncio
async def test_customer_unsupported_message_kind(storage, telegram_update, send_message_mock):
    update = await telegram_update(
        from_customer=True,
        sticker=Sticker(
            file_id="CAACAgQAAxkBAAIG-mWAv3L-CcgEs86whsGGTybEjjD6AAJ2AAMv3_gJdvG_3FZCYjgzBA",
            file_unique_id="AgADdgADL9_4CQ",
            width=512,
            height=512,
            is_animated=False,
            is_video=False,
            type=Sticker.REGULAR,
        ),
    )
    send_message_mock.assert_called_once_with(
        chat_id=update.effective_chat.id,
        text="😞 Sorry, this kind of content is not supported right now. "
        "Support agent will not see this message.",
        reply_to_message_id=update.message.message_id,
    )


@pytest.mark.asyncio
async def test_customer_text_message(storage, telegram_update):
    update = await telegram_update(from_customer=True, text="Hello there!")

    customer = await storage.create_or_update_customer(
        CustomerIdentification(telegram_user_id=update.effective_user.id)
    )
    assert customer.telegram_first_name == "Best"
    assert customer.telegram_last_name == "customer"

    conv = await storage.get_or_create_conversation(customer)
    assert conv.state == ConversationState.NEW
    assert len(conv.messages) == 1
    assert conv.messages[0].kind == MessageKind.FROM_CUSTOMER
    assert conv.messages[0].text == "Hello there!"


@pytest.mark.asyncio
async def test_agent_text_message(
    storage,
    backend,
    customer_telegram_chat,
    customer_conversation,
    send_message_mock,
):
    message = Message(
        kind=MessageKind.FROM_AGENT,
        time_utc=datetime.now(timezone.utc),
        text="How can I be of assistance?",
    )
    await backend.on_new_message_for_customer.trigger(
        NewMessageForCustomerEvent(
            customer=customer_conversation.customer,
            conversation=customer_conversation,
            message=message,
        )
    )

    send_message_mock.assert_called_once_with(
        chat_id=customer_telegram_chat.id, text="How can I be of assistance?"
    )


@pytest.mark.asyncio
async def test_customer_conversation_resolution(
    backend,
    telegram_update,
    customer_conversation,
    send_message_mock,
    edit_message_text_mock,
):
    placeholder = (await telegram_update(to_customer=True, text="whatever")).message
    send_message_mock.return_value = placeholder

    message = Message(kind=MessageKind.RESOLVED, time_utc=datetime.now(timezone.utc))
    await backend.on_new_message_for_customer.trigger(
        NewMessageForCustomerEvent(
            customer=customer_conversation.customer,
            conversation=customer_conversation,
            message=message,
        )
    )

    send_message_mock.assert_called_once_with(
        chat_id=placeholder.chat_id,
        text="✅ Conversation was marked as resolved. "
        "You can always start a new conversation by writing to this chat!",
    )
    edit_message_text_mock.assert_called_once_with(
        chat_id=placeholder.chat_id,
        message_id=placeholder.message_id,
        reply_markup=mock.ANY,
        text="✅ Conversation was marked as resolved. "
        "You can always start a new conversation by writing to this chat!\n\n"
        "⭐️ Please rate your experience with the support agent:",
    )

    reply_markup: InlineKeyboardMarkup = edit_message_text_mock.mock_calls[0].kwargs["reply_markup"]
    buttons = [button for row in reply_markup.inline_keyboard for button in row]
    button_texts = [button.text for button in buttons]
    assert button_texts == ["★☆☆☆☆", "★★☆☆☆", "★★★☆☆", "★★★★☆", "★★★★★"]

    edit_message_text_mock.reset_mock()

    callback_data = buttons[2].callback_data
    await telegram_update(
        from_customer=True,
        callback_message=placeholder,
        callback_data=callback_data,
    )

    edit_message_text_mock.assert_called_once_with(
        chat_id=placeholder.chat_id,
        message_id=placeholder.message_id,
        reply_markup=None,
        text="✅ Conversation was marked as resolved. "
        "You can always start a new conversation by writing to this chat!\n\n"
        "⭐️ How you rated this conversation: ★★★☆☆",
    )
