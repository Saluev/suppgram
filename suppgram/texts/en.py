from suppgram.entities import Conversation, Message, MessageKind
from suppgram.texts.interface import Texts


class EnglishTexts(Texts):
    telegram_customer_start_message = (
        "Welcome to support service! Please describe your problem."
    )
    telegram_customer_conversation_resolved_message = (
        "Conversation was marked as resolved. "
        "You can always start a new conversation by writing to this chat!"
    )
    telegram_manager_start_message = "Welcome to the support admin bot!"
    telegram_manager_permission_denied_message = (
        "You don't have permission to access manager functionality."
    )
    telegram_send_new_conversations_command_description = (
        "Send notifications about new conversations to this group."
    )
    telegram_agent_start_message = "Welcome to the support agent bot!"
    telegram_agent_permission_denied_message = (
        "You don't have permission to access support agent functionality."
    )
    telegram_workplace_is_not_assigned_message = (
        "This chat is not assigned to any ongoing "
        "conversation with a customer right now."
    )
    telegram_resolve_command_description = (
        "Mark conversation resolved and stop messaging with the customer."
    )
    telegram_agent_conversation_resolved_message = (
        "Conversation was marked as resolved. "
        "This chat is no longer assigned to a customer."
    )
    telegram_new_conversation_notification_placeholder = "New conversation!"

    def compose_telegram_new_conversation_notification(
        self, conversation: Conversation
    ) -> str:
        lines = [f"Conversation in status #{conversation.state.upper()}", ""]
        lines.extend(self._format_message(message) for message in conversation.messages)
        if agent := conversation.assigned_agent:
            agent_ref = (
                f"@{agent.telegram_username}"
                if agent.telegram_username
                else f"agent #{agent.id}"
            )
            lines.extend(["", f"Assigned to {agent_ref}"])
        return "\n".join(lines)

    def _format_message(self, message: Message) -> str:
        from_ = {
            MessageKind.FROM_CUSTOMER: "Customer",
            MessageKind.FROM_AGENT: "Agent",
        }[message.kind]
        return f"{from_}: {message.text}"

    telegram_assign_to_me_button_text = "Assign to me"
