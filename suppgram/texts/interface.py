from suppgram.entities import Conversation


class Texts:
    telegram_customer_start_message: str

    telegram_manager_start_message: str
    telegram_manager_permission_denied_message: str

    telegram_agent_start_message: str
    telegram_agent_permission_denied_message: str
    telegram_workplace_is_not_assigned_message: str

    telegram_send_new_conversations_command_description: str
    telegram_new_conversation_notification_placeholder: str

    def compose_telegram_new_conversation_notification(
        self, conversation: Conversation
    ) -> str:
        raise NotImplementedError

    telegram_assign_to_me_button_text: str
