from pubnub.models.consumer.pubsub import PNMessageResult

from suppgram.entities import CustomerIdentification


def make_customer_identification(message: PNMessageResult) -> CustomerIdentification:
    return CustomerIdentification(pubnub_user_id=message.publisher, pubnub_channel_id=message.channel)
