import logging

from suppgram.entities import (
    Conversation,
    Message,
    MessageKind,
    Agent,
)
from suppgram.texts.interface import TextsProvider, Text, Format

logger = logging.getLogger(__name__)


class EnglishTextsProvider(TextsProvider):
    telegram_customer_start_message = "👋 Welcome to support service! Please describe your problem."
    telegram_customer_conversation_resolved_message_placeholder = (
        "✅ Conversation was marked as resolved. "
        "You can always start a new conversation by writing to this chat!"
    )
    telegram_customer_conversation_resolved_message = (
        telegram_customer_conversation_resolved_message_placeholder + "\n\n"
        "⭐️ Please rate your experience with the support agent:"
    )

    def compose_customer_conversation_resolved_message(self, rating: int) -> str:
        return (
            self.telegram_customer_conversation_resolved_message_placeholder
            + "\n\n⭐️ How you rated this conversation: "
            + self.format_rating(rating)
        )

    telegram_manager_start_message = "🛠️ Welcome to the support admin bot!"
    telegram_manager_permission_denied_message = (
        "🚫 You don't have permission to access manager functionality."
    )
    telegram_agents_command_description = "Make all members of this group support agents."
    telegram_agents_command_success_message = (
        "I will now consider all members of this group support agents."
    )
    telegram_send_new_conversations_command_description = (
        "Send notifications about new conversations to this group."
    )
    telegram_send_new_conversations_command_success_message = (
        "I will now send notifications about new conversations to this group."
    )

    telegram_create_tag_command_description = "Create new tag to label conversations with"
    telegram_create_tag_permission_denied_message = (
        "🚫 You don't have permission to create new tags."
    )
    telegram_create_tag_usage_message = (
        "🧑‍🏫 Please specify new tag name after command:\n\n    /create_tag urgent"
    )
    telegram_tag_successfully_created_message = "✅ New tag has been successfully created."
    telegram_tag_already_exists_message = "⚠️ Tag with this name already exists!"

    telegram_agent_start_message = "👷 Welcome to the support agent bot!"
    telegram_agent_permission_denied_message = (
        "🚫 You don't have permission to access support agent functionality."
    )
    telegram_workplace_is_not_assigned_message = (
        "📭 This chat is not assigned to any ongoing " "conversation with a customer right now."
    )
    telegram_resolve_command_description = (
        "Mark conversation resolved and stop messaging with the customer."
    )
    telegram_postpone_command_description = (
        "Return the conversation to NEW status and stop messaging with the customer."
    )
    telegram_agent_conversation_resolved_message = (
        "✅ Conversation was marked as resolved. " "This chat is no longer assigned to a customer."
    )
    telegram_new_conversation_notification_placeholder = "❗️ New conversation!"

    customer_profile_header = "👤 Customer: {customer}"
    customer_profile_anonymous = "anonymous"
    customer_profile_contacts = "📒 Contacts: {contacts}"

    def compose_conversation_notification_header(self, conversation: Conversation) -> str:
        emoji = self.CONVERSATION_STATE_TO_EMOJI.get(conversation.state, "")
        return f"{emoji} Conversation in status #{conversation.state.upper()}"

    conversation_notification_assigned_to = "Assigned to {agent}"

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
            text=f"⚠️ {agent_ref}, please open @{telegram_bot_username} and "
            f"hit Start/Restart button to be able to communicate with the customer\\.",
            format=Format.TELEGRAM_MARKDOWN,
        )

    telegram_assign_to_me_button_text = "Assign to me"

    message_history_title = "🗂️ Message history\n"

    def format_history_message(self, message: Message) -> str:
        if message.kind == MessageKind.FROM_CUSTOMER:
            return f"👤 Customer: {message.text}"
        if message.kind == MessageKind.FROM_AGENT:
            return f"🧑‍💼 Agent: {message.text}"
        if message.kind == MessageKind.POSTPONED:
            return "⏳ Conversation was postponed."
        if message.kind == MessageKind.RESOLVED:
            return "✅ Conversation was resolved."
        logger.warning(f"Unsupported message kind: {message.kind.value!r}")
        return str(message.kind.value)
