import html
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Literal, Collection

from suppgram.emoji import EMOJI_SEQUENCE
from suppgram.entities import (
    Conversation,
    Customer,
    Tag,
    ConversationState,
    Agent,
    Message,
)
from suppgram.helpers import escape_markdown

logger = logging.getLogger(__name__)

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
        raise ValueError(f"text format {self.value!r} is not directly supported by Telegram")

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


class TextProvider:
    """Provides static texts and functions to compose dynamic texts where necessary."""

    telegram_customer_unsupported_message_content: str
    telegram_agent_unsupported_message_content: str

    telegram_customer_start_message: str
    telegram_customer_conversation_resolved_message_placeholder: str
    telegram_customer_conversation_resolved_message: str

    def compose_customer_conversation_resolved_message(self, rating: int) -> str:
        raise NotImplementedError

    telegram_manager_start_message: str
    telegram_manager_permission_denied_message: str
    telegram_agents_command_description: str
    telegram_agents_command_success_message: str
    telegram_send_new_conversations_command_description: str
    telegram_send_new_conversations_command_success_message: str

    telegram_report_command_description: str
    telegram_report_message_placeholder: str
    telegram_report_message: str

    # Tags
    telegram_create_tag_command_description: str
    telegram_create_tag_permission_denied_message: str
    telegram_create_tag_usage_message: str
    telegram_tag_already_exists_message: str
    telegram_tag_successfully_created_message: str

    def compose_add_tag_button_text(self, tag: Tag) -> str:
        return f"☐ {tag.name}"

    def compose_remove_tag_button_text(self, tag: Tag) -> str:
        return f"☑ {tag.name}"

    telegram_agent_start_message: str
    telegram_agent_permission_denied_message: str
    telegram_workplace_is_not_assigned_message: str
    telegram_resolve_command_description: str
    telegram_postpone_command_description: str
    telegram_agent_conversation_resolved_message: str

    telegram_new_conversation_notification_placeholder: str

    customer_profile_header: str
    customer_profile_anonymous: str
    customer_profile_contacts: str
    customer_rating_footer: str

    def compose_customer_profile(
        self, customer: Customer, allowed_formats: Collection[Format] = (Format.PLAIN,)
    ) -> Text:
        format_ = next(iter(allowed_formats))
        if Format.TELEGRAM_HTML in allowed_formats:
            format_ = Format.TELEGRAM_HTML
        elif Format.TELEGRAM_MARKDOWN in allowed_formats:
            format_ = Format.TELEGRAM_MARKDOWN

        full_name = (
            f"{customer.telegram_first_name or ''} {customer.telegram_last_name or ''}".strip()
            or self.customer_profile_anonymous
        )
        lines = [self.customer_profile_header.format(customer=full_name)]
        contacts = []
        if customer.telegram_user_id:
            contacts.append(
                self._format_telegram_mention(
                    telegram_user_id=customer.telegram_user_id,
                    telegram_first_name="Telegram",
                    telegram_last_name=None,
                    telegram_username=customer.telegram_username,
                    format_=format_,
                )
            )
        if contacts:
            lines.append(self.customer_profile_contacts.format(contacts=", ".join(contacts)))
        return Text(text="\n".join(lines), format=format_)

    CONVERSATION_STATE_TO_EMOJI = {
        ConversationState.NEW: "❗️",
        ConversationState.ASSIGNED: "⏳",
        ConversationState.RESOLVED: "✅",
    }

    def compose_conversation_notification_header(self, conversation: Conversation) -> str:
        raise NotImplementedError

    conversation_notification_assigned_to: str

    def compose_telegram_conversation_notification(self, conversation: Conversation) -> Text:
        profile = self.compose_customer_profile(
            conversation.customer,
            allowed_formats=Format.get_formats_supported_by_telegram(),
        )
        lines = [
            self.compose_conversation_notification_header(conversation),
            "",
            profile.text,
            "",
        ]
        lines.extend(self.format_history_message(message) for message in conversation.messages)

        if conversation.customer_rating is not None:
            rating = self.format_rating(conversation.customer_rating)
            lines.extend(("", self.customer_rating_footer.format(rating=rating)))

        if agent := conversation.assigned_agent:
            if agent.telegram_user_id:
                agent_ref = self._format_telegram_mention(
                    telegram_user_id=agent.telegram_user_id,
                    telegram_first_name=agent.telegram_first_name,
                    telegram_last_name=None,  # less formal
                    telegram_username=agent.telegram_username,
                    format_=profile.format,
                )
            else:
                logger.warning(f"Can't mention {agent} — unsupported agent frontend")
                agent_ref = f"#_{agent.id}"
            if conversation.customer_rating is None:
                lines.append("")
            lines.append(self.conversation_notification_assigned_to.format(agent=agent_ref))
        if conversation.tags:
            tags = [self._format_telegram_tag(tag) for tag in conversation.tags]
            lines.extend(("", " ".join(tags)))
        return Text(text="\n".join(lines), format=profile.format)

    def compose_nudge_to_start_bot_notification(
        self, agent: Agent, telegram_bot_username: str
    ) -> Text:
        raise NotImplementedError

    telegram_assign_to_me_button_text: str

    def _format_telegram_mention(
        self,
        telegram_user_id: int,
        telegram_first_name: Optional[str],
        telegram_last_name: Optional[str],
        telegram_username: Optional[str],
        format_: Format,
    ) -> str:
        full_name: str = (
            f"{telegram_first_name or ''} {telegram_last_name or ''}".strip()
            or telegram_username
            or str(telegram_user_id)
        )

        if format_ == Format.PLAIN:
            if not telegram_username:
                logger.warning(
                    f"Can't mention Telegram user {telegram_user_id} without username in plain format"
                )
            return f"@{telegram_username}" if telegram_username else full_name

        url = f"tg://user?id={telegram_user_id}"

        if format_ == Format.TELEGRAM_MARKDOWN:
            escaped_name = escape_markdown(full_name)
            return f"[{escaped_name}]({url})"

        if format_ == Format.TELEGRAM_HTML:
            escaped_name = html.escape(full_name)
            return f'<a href="{url}">{escaped_name}</a>'

        raise ValueError(f"text format {format_.value!r} is not supported")

    _TAG_REGEX = re.compile(rf"^\s*({EMOJI_SEQUENCE}*)(.*?)({EMOJI_SEQUENCE}*)\s*$")

    def _format_telegram_tag(self, tag: Tag) -> str:
        match = self._TAG_REGEX.match(tag.name)
        if match is not None:
            prefix, tag_name, suffix = match.groups()
        else:
            logger.warning(f"Couldn't match tag {tag.name!r} against emoji regex")
            prefix, tag_name, suffix = "", tag.name, ""
        tag_name = re.sub(r"\s+", "_", tag_name)
        tag_name = re.sub(r"\W+", "", tag_name)
        tag_name = tag_name.strip("_")
        if not tag_name:
            tag_name = f"tag_{tag.id}"  # assuming that database IDs are safe
        return f"{prefix}#{tag_name}{suffix}"

    message_history_title: str

    def format_history_message(self, message: Message) -> str:
        raise NotImplementedError

    def format_rating(self, rating: int) -> str:
        return "★" * rating + "☆" * (5 - rating)
