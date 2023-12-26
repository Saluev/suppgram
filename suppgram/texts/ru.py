import logging

from suppgram.entities import (
    Conversation,
    Message,
    MessageKind,
    Agent,
)
from suppgram.texts.interface import TextProvider, Text, Format

logger = logging.getLogger(__name__)


class RussianTextProvider(TextProvider):
    telegram_customer_unsupported_message_content = (
        "😞 Извините, такой тип сообщений пока не поддерживается. "
        "Агент поддержки не увидит это сообщение."
    )
    telegram_agent_unsupported_message_content = (
        "😞 Извините, такой тип сообщений пока не поддерживается. "
        "Пользователь не увидит это сообщение."
    )

    telegram_customer_start_message = (
        "👋 Добро пожаловать в службу поддержки! Опишите свою проблему."
    )
    telegram_customer_conversation_resolved_message_placeholder = (
        "✅ Обсуждение было завершено агентом поддержки. "
        "Вы всегда можете начать новое обсуждение, написав в этот чат!"
    )
    telegram_customer_conversation_resolved_message = (
        telegram_customer_conversation_resolved_message_placeholder + "\n\n"
        "⭐️ Пожалуйста, оцените работу агента:"
    )

    def compose_customer_conversation_resolved_message(self, rating: int) -> str:
        return (
            self.telegram_customer_conversation_resolved_message_placeholder
            + "\n\n⭐️ Ваша оценка работы агента: "
            + self.format_rating(rating)
        )

    telegram_manager_start_message = "🛠️ Добро пожаловать в бота-администратора службы поддержки!"
    telegram_manager_permission_denied_message = "🚫 У вас нет доступа к этой функциональности."
    telegram_agents_command_description = "Сделать всех участников этого чата агентами поддержки."
    telegram_agents_command_success_message = (
        "Теперь я буду считать всех участников этого чата агентами службы поддержки."
    )
    telegram_send_new_conversations_command_description = (
        "Отправлять уведомления о новых обсуждениях в этот чат."
    )
    telegram_send_new_conversations_command_success_message = (
        "Теперь я буду отправлять уведомления о всех новых обсуждениях в этот чат."
    )

    telegram_create_tag_command_description = "Создать новый тег для обсуждений."
    telegram_create_tag_permission_denied_message = "🚫 У вас нет доступа к созданию тегов."
    telegram_create_tag_usage_message = (
        "🧑‍🏫 Пожалуйста, укажите название нового тега после команды:\n\n    /create_tag urgent"
    )
    telegram_tag_successfully_created_message = "✅ Новый тег создан."
    telegram_tag_already_exists_message = "⚠️ Тег с таким названием уже есть!"

    telegram_agent_start_message = "👷 Добро пожаловать в бота для агентов поддержки!"
    telegram_agent_permission_denied_message = "🚫 У вас нет доступа к этой функциональности."
    telegram_workplace_is_not_assigned_message = (
        "📭 Сейчас этот чат не связан с кем-либо из пользователей."
    )
    telegram_resolve_command_description = "Пометить обсуждение как завершённое."
    telegram_postpone_command_description = (
        "Вернуть обсуждение в статус NEW и перестать переписываться с пользователем."
    )
    telegram_agent_conversation_resolved_message = (
        "✅ Обсуждение было завершено. Этот чат больше не связан с кем-либо из пользователей."
    )
    telegram_new_conversation_notification_placeholder = "❗️ Новое обсуждение!"

    customer_profile_header = "👤 Пользователь: {customer}"
    customer_profile_anonymous = "аноним"
    customer_profile_contacts = "📒 Контакты: {contacts}"

    def compose_conversation_notification_header(self, conversation: Conversation) -> str:
        emoji = self.CONVERSATION_STATE_TO_EMOJI.get(conversation.state, "")
        return f"{emoji} Обсуждение в статусе #{conversation.state.upper()}"

    conversation_notification_assigned_to = "Назначено, агент {agent}"

    def compose_nudge_to_start_bot_notification(
        self, agent: Agent, telegram_bot_username: str
    ) -> Text:
        if agent.telegram_user_id is None:
            raise RuntimeError("agent without Telegram account can't /start a bot!")
        agent_ref = self._format_telegram_mention(
            telegram_user_id=agent.telegram_user_id,
            telegram_first_name=agent.telegram_first_name,
            telegram_last_name=None,  # less formal
            telegram_username=agent.telegram_username,
            format_=Format.TELEGRAM_MARKDOWN,
        )
        return Text(
            text=f"⚠️ {agent_ref}, пожалуйста, откройте бота @{telegram_bot_username} и "
            f"нажмите кнопку Start или Restart, чтобы иметь возможность переписываться с пользователем. \\.",
            format=Format.TELEGRAM_MARKDOWN,
        )

    telegram_assign_to_me_button_text = "Назначить на меня"

    message_history_title = "🗂️ История сообщений\n"

    def format_history_message(self, message: Message) -> str:
        if message.kind == MessageKind.FROM_CUSTOMER:
            return f"👤 Пользователь: {message.text}"
        if message.kind == MessageKind.FROM_AGENT:
            return f"🧑‍💼 Агент: {message.text}"
        if message.kind == MessageKind.POSTPONED:
            return "⏳ Обсуждение было отложено."
        if message.kind == MessageKind.RESOLVED:
            return "✅ Обсуждение было завершено."
        logger.warning(f"Unsupported message kind: {message.kind.value!r}")
        return str(message.kind.value)
