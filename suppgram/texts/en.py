from suppgram.entities import Conversation, Message, MessageFrom
from suppgram.texts.interface import Texts


class EnglishTexts(Texts):
    telegram_customer_start_message = (
        "Welcome to support service! Please describe your problem."
    )
    telegram_manager_start_message = "Welcome to the support admin bot!"
    telegram_manager_permission_denied_message = (
        "You don't have permission to access manager functionality."
    )
    telegram_agent_start_message = "Welcome to the support agent bot!"
    telegram_agent_permission_denied_message = (
        "You don't have permission to access support agent functionality."
    )
    telegram_workplace_is_not_assigned_message = (
        "This chat is not assigned to any ongoing "
        "conversation with a customer right now."
    )
    telegram_new_conversation_notification_placeholder = "New conversation!"

    def compose_telegram_new_conversation_notification(
        self, conversation: Conversation
    ) -> str:
        lines = ["New conversation!", ""]
        lines.extend(self._format_message(message) for message in conversation.messages)
        return "\n".join(lines)

    def _format_message(self, message: Message) -> str:
        from_ = {
            MessageFrom.USER: "Customer",
            MessageFrom.AGENT: "Agent",
        }[message.from_]
        return f"{from_}: {message.text}"

    telegram_assign_to_me_button_text = "Assign to me"
