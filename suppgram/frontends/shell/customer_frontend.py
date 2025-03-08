import asyncio
import uuid
from datetime import datetime, timezone

import aioconsole

from suppgram.backend import Backend
from suppgram.entities import (
    NewMessageForCustomerEvent,
    MessageKind,
    CustomerIdentification,
    Message, MessageMediaKind,
)
from suppgram.frontend import CustomerFrontend
from suppgram.texts.interface import TextProvider


class ShellCustomerFrontend(CustomerFrontend):
    """
    Allows customers to access the support system via terminal.

    Useful for debug purposes.
    """

    def __init__(self, backend: Backend, texts: TextProvider):
        """
        Arguments:
            backend: used backend instance.
            texts: texts provider.
        """
        self._uuid = uuid.uuid4()
        self._backend = backend
        self._texts = texts

        backend.on_new_message_for_customer.add_handler(self._handle_new_message_for_customer_event)

    async def start(self):
        asyncio.create_task(self._run())

    async def _run(self):
        print(self._texts.telegram_customer_start_message)
        while True:
            text = await aioconsole.ainput("You: ")
            conversation = await self._backend.identify_customer_conversation(
                CustomerIdentification(shell_uuid=self._uuid)
            )
            await self._backend.process_message(
                conversation,
                Message(
                    kind=MessageKind.FROM_CUSTOMER,
                    time_utc=datetime.now(timezone.utc),
                    text=text,
                ),
            )

    async def _handle_new_message_for_customer_event(self, event: NewMessageForCustomerEvent):
        text = event.message.text or {MessageMediaKind.IMAGE: "[🖼️image]"}.get(event.message.media_kind, "")
        if event.message.kind == MessageKind.RESOLVED:
            text = self._texts.telegram_customer_conversation_resolved_message
        print("\rAgent:", text, "\nYou: ", end="")
