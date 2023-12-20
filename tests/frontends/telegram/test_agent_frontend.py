from datetime import datetime, timezone

import pytest
from telegram import Message as TMessage, User, Chat, ChatMember
from telegram.error import BadRequest

from suppgram.entities import Message, MessageKind

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_unauthorized_start(
    agent_apps, telegram_update, generate_telegram_id, send_message_mock
):
    user = User(id=generate_telegram_id(), first_name="Somebody", is_bot=False)
    chat = Chat(id=user.id, type=Chat.PRIVATE)
    update = await telegram_update(chat=chat, from_user=user, to_app=agent_apps[0], text="/start")
    send_message_mock.assert_called_once_with(
        chat_id=update.effective_chat.id,
        text="🚫 You don't have permission to access manager functionality.",
    )


@pytest.mark.asyncio
async def test_new_agent_start(
    agent_apps,
    agent_group,
    agent_telegram_chat,
    agent_telegram_user,
    telegram_update,
    send_message_mock,
    get_chat_member_mock,
):
    get_chat_member_mock.return_value = ChatMember(
        user=agent_telegram_user, status=ChatMember.MEMBER
    )
    update = await telegram_update(
        chat=agent_telegram_chat, from_user=agent_telegram_user, to_app=agent_apps[0], text="/start"
    )
    get_chat_member_mock.assert_called_once_with(
        chat_id=agent_group.telegram_chat_id, user_id=agent_telegram_user.id
    )
    send_message_mock.assert_called_once_with(
        chat_id=update.effective_chat.id, text="👷 Welcome to the support agent bot!"
    )


@pytest.mark.asyncio
async def test_preexisting_agent_start(telegram_update, workplaces, send_message_mock):
    update = await telegram_update(from_workplace=workplaces[0], text="/start")
    send_message_mock.assert_called_once_with(
        chat_id=update.effective_chat.id, text="👷 Welcome to the support agent bot!"
    )


@pytest.mark.asyncio
async def test_conversation_assignment(
    backend, customer, customer_conversation, agent, agent_send_message_mocks
):
    await backend.process_message(
        customer_conversation,
        Message(
            kind=MessageKind.FROM_CUSTOMER, time_utc=datetime.now(timezone.utc), text="Gamarjoba!"
        ),
    )
    await backend.assign_agent(agent, agent, customer_conversation.id)
    agent_send_message_mocks[0].assert_any_call(
        chat_id=agent.telegram_user_id,
        text=f'👤 Customer: Best customer\n📒 Contacts: <a href="tg://user?id={customer.telegram_user_id}">Telegram</a>',
        parse_mode="HTML",
    )
    agent_send_message_mocks[0].assert_called_with(
        chat_id=agent.telegram_user_id, text="Gamarjoba!"
    )


@pytest.mark.asyncio
async def test_nudge_to_start_bot(
    backend,
    telegram_update,
    generate_telegram_id,
    customer,
    customer_conversation,
    agent,
    agent_telegram_user,
    agent_group,
    workplaces,
    agent_send_message_mocks,
    manager_send_message_mock,
    get_chat_member_mock,
    delete_message_mock,
):
    agent_send_message_mocks[0].side_effect = BadRequest("Chat not found")
    get_chat_member_mock.return_value = ChatMember(
        user=agent_telegram_user, status=ChatMember.MEMBER
    )
    nudge_message_id = generate_telegram_id()
    manager_send_message_mock.return_value = TMessage(
        message_id=nudge_message_id,
        date=datetime.now(timezone.utc),
        chat=Chat(id=agent_group.telegram_chat_id, type=Chat.GROUP),
    )

    await backend.assign_agent(agent, agent, customer_conversation.id)
    agent_send_message_mocks[0].assert_called_once_with(
        chat_id=agent.telegram_user_id,
        text=f'👤 Customer: Best customer\n📒 Contacts: <a href="tg://user?id={customer.telegram_user_id}">Telegram</a>',
        parse_mode="HTML",
    )
    manager_send_message_mock.assert_called_once_with(
        chat_id=agent_group.telegram_chat_id,
        text=f"⚠️ [Agent](tg://user?id={agent.telegram_user_id}), please open @Agent0Bot and hit "
        "Start/Restart button to be able to communicate with the customer\\.",
        parse_mode="MarkdownV2",
    )

    agent_send_message_mocks[0].side_effect = None
    await telegram_update(from_workplace=workplaces[0], text="/start")
    delete_message_mock.assert_called_once_with(
        chat_id=agent_group.telegram_chat_id, message_id=nudge_message_id
    )
    agent_send_message_mocks[0].assert_any_call(
        chat_id=agent.telegram_user_id, text="👷 Welcome to the support agent bot!"
    )
    agent_send_message_mocks[0].assert_called_with(
        chat_id=agent.telegram_user_id,
        text=f'👤 Customer: Best customer\n📒 Contacts: <a href="tg://user?id={customer.telegram_user_id}">Telegram</a>',
        parse_mode="HTML",
    )


@pytest.mark.asyncio
async def test_agent_text_message_forwarding(
    backend,
    telegram_update,
    customer,
    customer_conversation,
    agent,
    workplaces,
    agent_send_message_mocks,
    customer_send_message_mock,
):
    await backend.assign_agent(agent, agent, customer_conversation.id)
    await telegram_update(from_workplace=workplaces[0], text="How can I help you?")
    customer_send_message_mock.assert_called_once_with(
        chat_id=customer.telegram_user_id, text="How can I help you?"
    )
