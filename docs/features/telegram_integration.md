# Telegram integraton

Configuring Telegram bots is pretty much covered in [Quickstart](../usage/quickstart.md)
section. Examples:

```shell
# Secrets in environment variables
export TELEGRAM_MANAGER_BOT_TOKEN="token"
export TELEGRAM_CUSTOMER_BOT_TOKEN="token"
export TELEGRAM_AGENT_BOT_TOKENS="token1 token2 ..."
python -m suppgram.cli.all_in_one ...

# Secrets in files
echo "token" > /secrets/manager_bot_token
echo "token" > /secrets/customer_bot_token
echo "token1 token2 ..." > /secrets/agent_bot_tokens
python -m suppgram.cli.all_in_one \
    --telegram-manager-bot-token-file /secrets/manager_bot_token \
    --telegram-customer-bot-token-file /secrets/customer_bot_token \
    --telegram-agent-bot-tokens-file /secrets/agent_bot_tokens \
    ...
```

## Bot commands

All bots update their command list on startup, so hints should be accessible
via Telegram interface (upon typing `/`).

Manager bot commands: 

* `/create_tag` — create new tag to label conversations with. Works in private chat with the bot.
* `/agents` — make all members of a group support agents **and** send notifications about new conversations to the 
  group. Works in group chats.
* `/send_new_conversations` — only send notifications about new conversations to a group. Works in group chats. May be
  useful to create a separate group without agents to overview all conversations.

Agent bot commands:

* `/postpone` — stop messaging with the customer currently assigned to this bot and return the conversation to NEW 
  status. 
* `/resolve` — stop messaging with the customer currently assigned to this bot and mark conversation resolved.
