import html
import logging
from typing import Optional, Collection

from suppgram.entities import (
    Conversation,
    Message,
    MessageKind,
    Customer,
    ConversationTag,
    Agent,
)
from suppgram.helpers import escape_markdown
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

    def compose_add_tag_button_text(self, tag: ConversationTag) -> str:
        return f"☐ {tag.name}"

    def compose_remove_tag_button_text(self, tag: ConversationTag) -> str:
        return f"☑ {tag.name}"

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

    # TODO move logic to base class, keep only string templates here
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
            or "anonymous"
        )
        lines = [f"👤 Customer: {full_name}"]
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
        lines.append("Contacts: " + ", ".join(contacts))
        return Text(text="\n".join(lines), format=format_)

    def compose_telegram_new_conversation_notification(self, conversation: Conversation) -> Text:
        profile = self.compose_customer_profile(
            conversation.customer,
            allowed_formats=Format.get_formats_supported_by_telegram(),
        )
        emoji = self.CONVERSATION_STATE_TO_EMOJI.get(conversation.state, "")
        lines = [
            f"{emoji} Conversation in status #{conversation.state.upper()}",
            "",
            profile.text,
            "",
        ]
        lines.extend(self.format_history_message(message) for message in conversation.messages)
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
            lines.extend(("", f"Assigned to {agent_ref}"))
        if conversation.tags:
            tags = [self._format_telegram_tag(tag) for tag in conversation.tags]
            lines.extend(("", " ".join(tags)))
        return Text(text="\n".join(lines), format=profile.format)

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
