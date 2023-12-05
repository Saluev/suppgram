import os
from dataclasses import dataclass
from typing import Optional

from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub_asyncio import PubNubAsyncio

from suppgram.frontends.pubnub.errors import MissingCredentials


@dataclass(frozen=True)
class Configuration:
    pn_config: PNConfiguration
    pn_token: Optional[str]

    def instantiate_async(self) -> PubNubAsyncio:
        pubnub = PubNubAsyncio(self.pn_config)
        if self.pn_token:
            pubnub.set_token(self.pn_token)
        return pubnub


def make_pubnub_configuration(pubnub_user_id: str) -> Configuration:
    pn_config = PNConfiguration()
    pn_config.subscribe_key = _get_env_variable("PUBNUB_SUBSCRIBE_KEY")
    pn_config.publish_key = _get_env_variable("PUBNUB_PUBLISH_KEY")
    pn_config.secret_key = os.environ.get("PUBNUB_SECRET_KEY")
    pn_config.uuid = pubnub_user_id
    pn_token = os.environ.get("PUBNUB_TOKEN")

    if not pn_config.secret_key and not pn_token:
        raise MissingCredentials(
            "both PUBNUB_SECRET_KEY and PUBNUB_TOKEN environment variables are not set — "
            "the app won't have permissions to do anything.\n\n"
            "Provide PubNub secret key if you trust the app; otherwise, "
            "create access token with necessary permissions (User.get for the support user, "
            "Channel.read, Channel.write and Channel.join for the support channels group)."
        )

    return Configuration(pn_config=pn_config, pn_token=pn_token)


def _get_env_variable(name: str) -> str:
    try:
        return os.environ[name]
    except KeyError as exc:
        raise MissingCredentials(
            f"required environment variable {name} is not set"
        ) from exc
