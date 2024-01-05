# PubNub integrations

[PubNub](https://pubnub.com/) operates channels and users within channels. It also allows 
gathering chats into [channel groups](https://www.pubnub.com/docs/sdks/python/api-reference/channel-groups).

Suppgram integration presumes there is a single channel group all support channels belong to.
All messages from support agents will be authored by a single PubNub user.
All messages written to these channels by users other than the support user are considered
messages from customers and will be forwarded to agents.

To configure PubNub, you will need to specify a number of environment variables and flags:
```shell
export PUBNUB_PUBLISH_KEY="publish_key"
export PUBNUB_SUBSCRIBE_KEY="subscribe_key"
export PUBNUB_SECRET_KEY="secret_key"
python -m suppgram.cli.all_in_one \
    --pubnub-user-id "support_user_id" \
    --pubnub-channel-group "support_channel_group" \
    ...
```
Secret key is optional; if not specified, it is your responsibility to ensure that 
support user has all necessary permissions to read and write to channels.

Since there is no strict structure of messages within PubNub, but rather they are
arbitrary JSONs, you might need to implement a custom encoder/decoder for them:

::: suppgram.frontends.pubnub.MessageConverter
    handler: python
    options:
      show_root_heading: true
      show_source: false
      show_bases: false
      heading_level: 2

Default implementation is `suppgram.frontends.pubnub.DefaultMessageConverter`. It may be used with
sandbox credentials to test how it works. To override it, use `--pubnub-message-converter` flag:
```shell
python -m suppgram.cli.all_in_one \
  --pubnub-message-converter mymodule.MyConverter \
  ...
```

For testing purposes you can also use `suppgram.cli.pubnub_customer_client` tool, accepting basically
the same list of environment variables and command line arguments:
```shell
$ python -m suppgram.cli.pubnub_customer_client --help
Usage: python -m suppgram.cli.pubnub_customer_client [OPTIONS]

Options:
  --pubnub-user-id TEXT           PubNub user ID [default: random UUID]
  --pubnub-channel TEXT           PubNub channel for communication with
                                  support [default: UUID-support]
  --pubnub-channel-group TEXT     PubNub channel group to add channel to
                                  [default: support]
  --pubnub-message-converter TEXT
                                  Class converting messages between PubNub
                                  JSONs and suppgram Message objects
                                  [default: suppgram.frontends.pubnub.DefaultM
                                  essageConverter]
  --help                          Show this message and exit.
```
**Note** that user ID here is **not** support user ID as before, but rather customer user ID. 
It can be omitted; then it will be generated randomly. It will probably not work without secret 
key though, since now we'll have to get some permissions dynamically.
