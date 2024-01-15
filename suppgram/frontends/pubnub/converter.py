import abc
from datetime import datetime, timezone
from importlib import import_module
from typing import Any

from pubnub.models.consumer.pubsub import PNMessageResult

from suppgram.entities import Message, MessageKind


def make_pubnub_message_converter(converter_class_path: str) -> "MessageConverter":
    (
        converter_module_name,
        converter_class_name,
    ) = converter_class_path.rsplit(".", 1)
    converter_class = getattr(import_module(converter_module_name), converter_class_name)
    return converter_class()


class MessageConverter(abc.ABC):
    """Converts messages from project-specific JSON to [Message][suppgram.entities.Message] dataclass and vice-versa.

    Methods:
        convert_from_pubnub: convert from project-specific JSON received from PubNub
        convert_to_pubnub: convert to project-specific JSON to be sent to PubNub"""

    @abc.abstractmethod
    def convert_from_pubnub(self, message: PNMessageResult) -> Message:
        pass

    @abc.abstractmethod
    def convert_to_pubnub(self, message: Message) -> Any:
        pass


class DefaultMessageConverter(MessageConverter):
    _ISO_8601_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"

    def convert_from_pubnub(self, message: PNMessageResult) -> Message:
        return Message(
            kind=MessageKind(message.message["kind"]),
            time_utc=datetime.strptime(message.message["time"], self._ISO_8601_FORMAT).astimezone(
                timezone.utc
            ),
            text=message.message.get("text"),
        )

    def convert_to_pubnub(self, message: Message) -> Any:
        return {
            "kind": message.kind.value,
            "time": message.time_utc.strftime(self._ISO_8601_FORMAT),
            "text": message.text,
        }
