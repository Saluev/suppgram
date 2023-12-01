import html
import logging
from typing import Optional, Collection

from suppgram.entities import Conversation, Message, MessageKind, Customer
from suppgram.helpers import escape_markdown
from suppgram.texts.interface import TextsProvider, Text, Format

logger = logging.getLogger(__name__)


class EnglishTextsProvider(TextsProvider):
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
            or "Anonymous"
        )
        lines = [full_name]
        contacts = []
        if customer.telegram_user_id:
            contacts.append(
                self._format_telegram_mention(
                    telegram_user_id=customer.telegram_user_id,
                    telegram_first_name=customer.telegram_first_name,
                    telegram_last_name=customer.telegram_last_name,
                    telegram_username=customer.telegram_username,
                    format_=format_,
                )
            )
        lines.append("Contacts: " + ", ".join(contacts))
        return Text(text="\n".join(lines), format=format_)

    def compose_telegram_new_conversation_notification(
        self, conversation: Conversation
    ) -> Text:
        profile = self.compose_customer_profile(
            conversation.customer,
            allowed_formats=Format.get_formats_supported_by_telegram(),
        )
        lines = [
            f"Conversation in status #{conversation.state.upper()}",
            "",
            f"Customer: {profile.text}",
            "",
        ]
        lines.extend(self._format_message(message) for message in conversation.messages)
        if agent := conversation.assigned_agent:
            agent_ref = self._format_telegram_mention(
                telegram_user_id=agent.telegram_user_id,
                telegram_first_name=agent.telegram_first_name,
                telegram_last_name=None,  # less formal
                telegram_username=agent.telegram_username,
                format_=profile.format,
            )
            lines.extend(["", f"Assigned to {agent_ref}"])
        return Text(text="\n".join(lines), format=profile.format)

    def _format_message(self, message: Message) -> str:
        from_ = {
            MessageKind.FROM_CUSTOMER: "Customer",
            MessageKind.FROM_AGENT: "Agent",
        }[message.kind]
        return f"{from_}: {message.text}"

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
