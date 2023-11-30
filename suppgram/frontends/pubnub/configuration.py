import os

from pubnub.pnconfiguration import PNConfiguration

from suppgram.frontends.pubnub.errors import MissingCredentials


def make_pubnub_configuration(pubnub_user_id: str) -> PNConfiguration:
    pnconfig = PNConfiguration()
    pnconfig.subscribe_key = _get_env_variable("PUBNUB_SUBSCRIBE_KEY")
    pnconfig.publish_key = _get_env_variable("PUBNUB_PUBLISH_KEY")
    pnconfig.secret_key = _get_env_variable(
        "PUBNUB_SECRET_KEY"
    )  # TODO accept token instead of secret key, handle exceptions
    pnconfig.uuid = pubnub_user_id
    return pnconfig


def _get_env_variable(name: str) -> str:
    try:
        return os.environ[name]
    except KeyError as exc:
        raise MissingCredentials(
            f"required environment variable {name} is not set"
        ) from exc
