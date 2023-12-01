from dataclasses import dataclass
from enum import Enum
from typing import Optional, Literal, Collection

from suppgram.entities import Conversation, Customer, ConversationTag

TelegramParseMode = Optional[Literal["MarkdownV2", "HTML"]]


class Format(str, Enum):
    PLAIN = "plain"
    TELEGRAM_MARKDOWN = "telegram_markdown"
    TELEGRAM_HTML = "telegram_html"

    def convert_to_parse_mode(self) -> TelegramParseMode:
        if self == Format.PLAIN:
            return None
        if self == Format.TELEGRAM_MARKDOWN:
            return "MarkdownV2"
        if self == Format.TELEGRAM_HTML:
            return "HTML"
        raise ValueError(
            f"text format {self.value!r} is not directly supported by Telegram"
        )

    @classmethod
    def get_formats_supported_by_telegram(cls) -> Collection["Format"]:
        return {cls.PLAIN, cls.TELEGRAM_MARKDOWN, cls.TELEGRAM_HTML}


@dataclass(frozen=True)
class Text:
    text: str
    format: Format = Format.PLAIN

    @property
    def parse_mode(self) -> Optional[str]:
        return self.format.convert_to_parse_mode()


class TextsProvider:
    telegram_customer_start_message: str
    telegram_customer_conversation_resolved_message_placeholder: str
    telegram_customer_conversation_resolved_message: str

    def compose_customer_conversation_resolved_message(self, rating: int) -> str:
        pass

    telegram_manager_start_message: str
    telegram_manager_permission_denied_message: str
    telegram_send_new_conversations_command_description: str

    # Tags
    telegram_create_tag_command_description: str
    telegram_create_tag_permission_denied_message: str
    telegram_create_tag_usage_message: str
    telegram_tag_already_exists_message: str
    telegram_tag_successfully_created_message: str

    def compose_add_tag_button_text(self, tag: ConversationTag) -> str:
        raise NotImplementedError

    def compose_remove_tag_button_text(self, tag: ConversationTag) -> str:
        raise NotImplementedError

    telegram_agent_start_message: str
    telegram_agent_permission_denied_message: str
    telegram_workplace_is_not_assigned_message: str
    telegram_resolve_command_description: str
    telegram_agent_conversation_resolved_message: str

    telegram_new_conversation_notification_placeholder: str

    def compose_customer_profile(
        self, customer: Customer, allowed_formats: Collection[Format] = (Format.PLAIN,)
    ) -> Text:
        raise NotImplementedError

    def compose_telegram_new_conversation_notification(
        self, conversation: Conversation
    ) -> Text:
        raise NotImplementedError

    telegram_assign_to_me_button_text: str

    def format_rating(self, rating: int) -> str:
        return "★" * rating + "☆" * (5 - rating)
