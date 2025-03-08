import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import aioconsole
import click
from pubnub.callbacks import SubscribeCallback
from pubnub.models.consumer.common import PNStatus
from pubnub.models.consumer.pubsub import PNMessageResult, PNPresenceEventResult
from pubnub.pubnub import PubNub

from suppgram.entities import MessageKind, Message, MessageMediaKind
from suppgram.frontends.pubnub.configuration import make_pubnub_configuration
from suppgram.frontends.pubnub.converter import (
    MessageConverter,
    make_pubnub_message_converter,
)


@click.command()
@click.option("--pubnub-user-id", default=None, help="PubNub user ID [default: random UUID]")
@click.option(
    "--pubnub-channel",
    default=None,
    help="PubNub channel for communication with support [default: UUID-support]",
)
@click.option(
    "--pubnub-channel-group",
    default="support",
    show_default=True,
    help="PubNub channel group to add channel to",
)
@click.option(
    "--pubnub-message-converter",
    "pubnub_message_converter_class_path",
    default="suppgram.frontends.pubnub.DefaultMessageConverter",
    show_default=True,
    help="Class converting messages between PubNub JSONs and suppgram Message objects",
)
def run_pubnub_customer_client(
    pubnub_user_id: Optional[str],
    pubnub_channel: Optional[str],
    pubnub_channel_group: str,
    pubnub_message_converter_class_path: str,
):
    loop = asyncio.get_event_loop()

    if not pubnub_user_id:
        pubnub_user_id = uuid4().hex
    if not pubnub_channel:
        pubnub_channel = f"{pubnub_user_id}-support"
    pubnub_configuration = make_pubnub_configuration(pubnub_user_id)
    pubnub = pubnub_configuration.instantiate_async()

    converter = make_pubnub_message_converter(pubnub_message_converter_class_path)

    async def _run():
        await pubnub.add_channel_to_channel_group().channels([pubnub_channel]).channel_group(
            pubnub_channel_group
        ).future()
        pubnub.add_listener(_SubscribeCallback(converter))
        pubnub.subscribe().channels([pubnub_channel]).execute()
        while True:
            text = await aioconsole.ainput("You: ")
            message = Message(
                kind=MessageKind.FROM_CUSTOMER,
                time_utc=datetime.now(timezone.utc),
                text=text,
            )
            converted = converter.convert_to_pubnub(message)
            await pubnub.publish().message(converted).channel(pubnub_channel).future()

    loop.run_until_complete(_run())


class _SubscribeCallback(SubscribeCallback):
    def __init__(self, message_converter: MessageConverter) -> None:
        self._message_converter = message_converter

    def status(self, pubnub: PubNub, status: PNStatus) -> None:
        pass

    def message(self, pubnub: PubNub, message: PNMessageResult) -> None:
        converted = self._message_converter.convert_from_pubnub(message)
        if converted.kind == MessageKind.FROM_CUSTOMER:
            return
        prefix = {
            MessageKind.FROM_AGENT: "\rAgent: ",
            MessageKind.RESOLVED: "\rConversation was marked as resolved.",
        }.get(converted.kind, f"\r{converted.kind.value}")
        text = converted.text or {MessageMediaKind.IMAGE: "[🖼️image]"}.get(converted.media_kind, "")
        print(f"{prefix}{text}\nYou: ", end="")

    def presence(self, pubnub: PubNub, presence: PNPresenceEventResult) -> None:
        pass


if __name__ == "__main__":
    run_pubnub_customer_client()
