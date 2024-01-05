import asyncio

from pubnub.callbacks import SubscribeCallback
from pubnub.models.consumer.common import PNStatus
from pubnub.models.consumer.pubsub import PNPresenceEventResult, PNMessageResult
from pubnub.pubnub import PubNub

from suppgram.backend import Backend
from suppgram.entities import MessageKind, NewMessageForCustomerEvent
from suppgram.frontend import CustomerFrontend
from suppgram.frontends.pubnub.configuration import Configuration
from suppgram.frontends.pubnub.converter import MessageConverter
from suppgram.frontends.pubnub.identification import make_customer_identification


class PubNubCustomerFrontend(CustomerFrontend):
    """
    Allows customers to access the support system via PubNub channels.

    All channels from a specific PubNub channel group will be considered
    individual chats with support. When agent responds, agent's message content
    will be copied and sent to the customer on behalf of a particular PubNub user
    (e.g. with user ID "support").
    """

    def __init__(
        self,
        backend: Backend,
        message_converter: MessageConverter,
        pubnub_channel_group: str,
        pubnub_configuration: Configuration,  # user ID to send messages from is also in there
    ):
        """
        This constructor should not be used directly; use [Builder][suppgram.builder.Builder] instead.

        Arguments:
            backend: used backend instance.
            message_converter: helper object responsible for converting messages between Suppgram dataclasses
                               and project-specific PubNub JSONs.
            pubnub_channel_group: name of PubNub channel group which includes all individual chats with support.
                                  Will be used to subscribe for updates from all those chats at once.
            pubnub_configuration: PubNub client configuration.
        """
        self._message_converter = message_converter
        self._pubnub = pubnub_configuration.instantiate_async()
        self._pubnub.add_listener(_SubscribeCallback(backend, message_converter))
        self._pubnub_channel_group = pubnub_channel_group
        backend.on_new_message_for_customer.add_handler(self._handle_new_message_for_customer_event)

    async def start(self):
        self._pubnub.subscribe().channel_groups([self._pubnub_channel_group]).execute()

    async def _handle_new_message_for_customer_event(self, event: NewMessageForCustomerEvent):
        customer = event.conversation.customer
        if customer.pubnub_user_id is None or customer.pubnub_channel_id is None:
            return
        converted = self._message_converter.convert_to_pubnub(event.message)
        (
            await self._pubnub.publish()
            .channel(customer.pubnub_channel_id)
            .message(converted)
            .future()
        )


class _SubscribeCallback(SubscribeCallback):
    def __init__(self, backend: Backend, message_converter: MessageConverter):
        self._backend = backend
        self._message_converter = message_converter

    def status(self, pubnub: PubNub, status: PNStatus):
        pass

    def message(self, pubnub: PubNub, message: PNMessageResult):
        loop = asyncio.get_event_loop()
        loop.create_task(self._message(message))

    async def _message(self, message: PNMessageResult):
        converted = self._message_converter.convert_from_pubnub(message)
        if converted.kind != MessageKind.FROM_CUSTOMER:
            return
        identification = make_customer_identification(message)
        conversation = await self._backend.identify_customer_conversation(identification)
        await self._backend.process_message(conversation, converted)

    def presence(self, pubnub: PubNub, presence: PNPresenceEventResult):
        pass
