from datetime import datetime, timezone

import pytest
from telegram import Update, Message, Chat, User, MessageEntity

from suppgram.entities import CustomerIdentification, ConversationState, MessageKind

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_customer_frontend(
    storage, customer_app, customer_frontend, generate_telegram_id, send_message_mock
):
    customer_telegram_user_id = generate_telegram_id()
    user = User(id=customer_telegram_user_id, first_name="Best", last_name="customer", is_bot=False)
    chat = Chat(id=customer_telegram_user_id, type=Chat.PRIVATE)
    message = Message(
        message_id=generate_telegram_id(),
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=user,
        text="/start",
        entities=[MessageEntity(type=MessageEntity.BOT_COMMAND, offset=0, length=len("/start"))],
    )
    message.set_bot(customer_app.bot)
    await customer_app.process_update(Update(update_id=0, message=message))
    send_message_mock.assert_called_once_with(
        chat.id, "👋 Welcome to support service! Please describe your problem."
    )

    message = Message(
        message_id=generate_telegram_id(),
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=user,
        text="Hello there!",
    )
    await customer_app.process_update(Update(update_id=1, message=message))

    customer = await storage.create_or_update_customer(
        CustomerIdentification(telegram_user_id=customer_telegram_user_id)
    )
    assert customer.telegram_first_name == "Best"
    assert customer.telegram_last_name == "customer"

    conv = await storage.get_or_create_conversation(customer)
    assert conv.state == ConversationState.NEW
    assert len(conv.messages) == 1
    assert conv.messages[0].kind == MessageKind.FROM_CUSTOMER
    assert conv.messages[0].text == "Hello there!"
