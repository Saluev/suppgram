# All-in-one CLI

The easiest way to run Suppgram is to use all-in-one CLI, as shown in [Quickstart](quickstart.md):
```shell
$ python -m suppgram.cli.all_in_one \
         --sqlalchemy-uri sqlite+aiosqlite:///test.db \
         --telegram-owner-id <your Telegram user ID>
```
You can run it with `--help` flag to see usage instructions:
```shell
$ python -m suppgram.cli.all_in_one --help
Usage: python -m suppgram.cli.all_in_one [OPTIONS]

Options:
  --loglevel [DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL]
                                  Log level
  --sqlalchemy-uri TEXT           SQLAlchemy connection URI. Alternatively,
                                  environment variable SQLALCHEMY_URI may be
                                  used
  --mongodb-uri TEXT              MongoDB connection URI. Alternatively,
                                  environment variable MONGODB_URI may be used
  --mongodb-database TEXT         MongoDB database name. If not specified,
                                  will connect to the default database
                                  specified in the URI
  --texts TEXT                    Class with texts  [default:
                                  suppgram.texts.en.EnglishTextProvider]
  --telegram-customer-bot-token-file FILE
                                  Path to file storing token for Telegram bot
                                  serving customers. Alternatively,
                                  environment variable
                                  TELEGRAM_CUSTOMER_BOT_TOKEN may be used
  --telegram-manager-bot-token-file FILE
                                  Path to file storing token for Telegram
                                  manager bot. Alternatively, environment
                                  variable TELEGRAM_MANAGER_BOT_TOKEN may be
                                  used
  --telegram-agent-bot-tokens-file FILE
                                  Path to file storing token(s) for Telegram
                                  bot(s) serving agents. Alternatively,
                                  environment variable
                                  TELEGRAM_AGENT_BOT_TOKENS may be used
  --telegram-owner-id INTEGER     ID of Telegram user who will be granted all
                                  permissions
  --customer-shell                Run shell-based customer interface
  --pubnub-user-id TEXT           PubNub user ID to send support messages from
                                  [default: support]
  --pubnub-channel-group TEXT     PubNub channel group containing chats with
                                  support  [default: support]
  --pubnub-message-converter TEXT
                                  Class converting messages between PubNub
                                  JSONs and suppgram.entities.Message objects
                                  [default: suppgram.frontends.pubnub.DefaultM
                                  essageConverter]
  --help                          Show this message and exit.
```
It is recommended to prefer environment variables over command line arguments
for sensitive data, e.g. for SQLAlchemy URI if it contains username and/or password.

Details on particular integrations (SQLAlchemy, MongoDB, Telegram, PubNub, ...) are
in the next chapters of the documentation.

An alternative to the CLI is programmatic configuration via [Builder][suppgram.builder.Builder] component.
