# Bridges

Bridges are components designed to connect different storages and frontends. For example,
Telegram frontend may require storing something in a persistent storage; since the data is
frontend-specific, we shouldn't add corresponding methods to [Storage][suppgram.storage.Storage]
interface, but rather create a separate component using the same database.

::: suppgram.frontends.telegram.TelegramStorage
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 2

<hr/>

::: suppgram.bridges.sqlalchemy_telegram.SQLAlchemyTelegramBridge
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 2

<hr/>

::: suppgram.bridges.mongodb_telegram.MongoDBTelegramBridge
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 2
