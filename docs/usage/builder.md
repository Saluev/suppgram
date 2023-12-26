# Builder

Suppgram application can be constructed programmatically
within a Python script with Builder component which implements
traditional [Builder pattern](https://refactoring.guru/design-patterns/builder).
For example, code doing the same as CLI call from [Quickstart](quickstart.md) would look like this:

```python
import asyncio

from suppgram.builder import Builder

builder = (
    Builder()
    .with_sqlalchemy_storage("sqlite+aiosqlite:///test.db")
    .with_telegram_manager_frontend("<secret token of Manager bot>", your_Telegram_user_ID)
    .with_telegram_customer_frontend("<secret token of Customer bot>")
    .with_telegram_agent_frontend(["<secret token of Agent bot>"])
    .build()
)
loop = asyncio.get_event_loop()
loop.run_until_complete(builder.start())
loop.run_forever()
```


::: suppgram.builder.Builder
    handler: python
    options:
      show_root_heading: true
      show_source: false
      show_if_no_docstring: true
      heading_level: 2
