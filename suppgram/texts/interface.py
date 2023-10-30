from suppgram.entities import Conversation


class Texts:
    welcome_message: str
    telegram_workplace_is_not_assigned: str
    telegram_new_conversation_notification_placeholder: str

    def compose_telegram_new_conversation_notification(
        self, conversation: Conversation
    ) -> str:
        pass

    telegram_assign_to_me_button: str
