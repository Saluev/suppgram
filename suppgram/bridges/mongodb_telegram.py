from datetime import timezone
from typing import List, Optional, Any, Iterable, Mapping, Dict

from bson import CodecOptions, ObjectId
from motor.core import AgnosticDatabase
from pymongo import ReturnDocument

from suppgram.frontends.telegram.storage import (
    TelegramStorage,
    TelegramMessage,
    TelegramMessageKind,
    TelegramChat,
    TelegramChatRole,
)
from suppgram.storages.mongodb.collections import Document


class MongoDBTelegramBridge(TelegramStorage):
    """Implementation of [Storage][suppgram.storage.Storage] for MongoDB
    via [Motor](https://motor.readthedocs.io/) library."""

    def __init__(
        self,
        database: AgnosticDatabase,
        chat_collection_name: str = "suppgram_telegram_chats",
        messages_collection_name: str = "suppgram_telegram_messages",
    ):
        """
        Parameters:
            database: asyncio-compatible Motor MongoDB database to store data in
            chat_collection_name: name of MongoDB collection to store data on Telegram chats in
            messages_collection_name: name of MongoDB collection to store references to Telegram messages in
        """
        codec_options: CodecOptions = CodecOptions(tz_aware=True, tzinfo=timezone.utc)
        self._chat_collection = database.get_collection(chat_collection_name, codec_options)
        self._message_collection = database.get_collection(messages_collection_name, codec_options)

    async def get_chat(self, telegram_chat_id: int) -> TelegramChat:
        filter_ = self._make_chat_filter(telegram_chat_id)
        doc = await self._chat_collection.find_one(filter_)
        if doc is None:
            raise ValueError(f"couldn't find Telegram chat {telegram_chat_id}")
        return self._convert_to_chat(doc)

    async def find_chats_by_ids(self, telegram_chat_ids: List[int]) -> List[TelegramChat]:
        filter_ = self._make_chats_filter(telegram_chat_ids)
        docs = await self._chat_collection.find(filter_).to_list(None)
        return [self._convert_to_chat(doc) for doc in docs]

    async def create_or_update_chat(self, telegram_chat_id: int) -> TelegramChat:
        filter_ = self._make_chat_filter(telegram_chat_id)
        update = self._make_chat_update()
        doc = await self._chat_collection.find_one_and_update(
            filter_, update, upsert=True, return_document=ReturnDocument.AFTER
        )
        return self._convert_to_chat(doc)

    async def add_chat_roles(self, telegram_chat_id: int, *roles: TelegramChatRole):
        filter_ = self._make_chat_filter(telegram_chat_id)
        update = self._make_chat_roles_update(roles)
        result = await self._chat_collection.update_one(filter_, update)
        if result.matched_count == 0:
            raise ValueError(f"couldn't find Telegram chat {telegram_chat_id}")

    async def get_chats_by_role(self, role: TelegramChatRole) -> List[TelegramChat]:
        filter_ = self._make_chat_filter_by_role(role)
        docs = await self._chat_collection.find(filter_).to_list(None)
        return [self._convert_to_chat(doc) for doc in docs]

    def _make_chat_filter(self, telegram_chat_id: int) -> Document:
        return {"_id": telegram_chat_id}

    def _make_chats_filter(self, telegram_chat_ids: List[int]) -> Document:
        return {"_id": {"$in": telegram_chat_ids}}

    def _make_chat_filter_by_role(self, role: TelegramChatRole) -> Document:
        return {"roles": role.value}

    def _make_chat_update(self) -> Document:
        return {"$setOnInsert": {"roles": []}}

    def _make_chat_roles_update(self, roles: Iterable[TelegramChatRole]) -> Document:
        return {"$addToSet": {"roles": {"$each": [role.value for role in roles]}}}

    def _convert_to_chat(self, doc: Document) -> TelegramChat:
        return TelegramChat(
            telegram_chat_id=doc["_id"],
            roles=frozenset(TelegramChatRole(role) for role in doc.get("roles", [])),
        )

    async def insert_message(
        self,
        telegram_bot_id: int,
        chat: TelegramChat,
        telegram_message_id: int,
        kind: TelegramMessageKind,
        *,
        agent_id: Optional[Any] = None,
        customer_id: Optional[Any] = None,
        conversation_id: Optional[Any] = None,
        telegram_bot_username: Optional[str] = None,
    ) -> TelegramMessage:
        doc = {
            "_id": self._compose_message_id(chat.telegram_chat_id, telegram_message_id),
            "telegram_bot_id": telegram_bot_id,
            "kind": kind,
        }
        if agent_id is not None:
            doc["agent_id"] = ObjectId(agent_id)
        if customer_id is not None:
            doc["customer_id"] = ObjectId(customer_id)
        if conversation_id is not None:
            doc["conversation_id"] = ObjectId(conversation_id)
        if telegram_bot_username is not None:
            doc["telegram_bot_username"] = telegram_bot_username
        await self._message_collection.insert_one(doc)
        return self._convert_to_message(doc, {chat.telegram_chat_id: chat})

    async def get_message(self, chat: TelegramChat, telegram_message_id: int) -> TelegramMessage:
        filter_ = {"_id": self._compose_message_id(chat.telegram_chat_id, telegram_message_id)}
        doc = await self._message_collection.find_one(filter_)
        if doc is None:
            raise ValueError(
                f"couldn't find Telegram message {telegram_message_id} in chat {chat.telegram_chat_id}"
            )
        return self._convert_to_message(doc, chats={chat.telegram_chat_id: chat})

    async def get_messages(
        self,
        kind: TelegramMessageKind,
        *,
        agent_id: Optional[Any] = None,
        conversation_id: Optional[Any] = None,
        telegram_bot_username: Optional[str] = None,
    ) -> List[TelegramMessage]:
        filter_: Dict[str, Any] = {"kind": kind}
        if agent_id is not None:
            filter_["agent_id"] = ObjectId(agent_id)
        if conversation_id is not None:
            filter_["conversation_id"] = ObjectId(conversation_id)
        if telegram_bot_username is not None:
            filter_["telegram_bot_username"] = telegram_bot_username
        docs = await self._message_collection.find(filter_).to_list(None)
        return await self._convert_to_messages(docs)

    async def delete_messages(self, messages: List[TelegramMessage]):
        message_ids = [
            self._compose_message_id(message.chat.telegram_chat_id, message.telegram_message_id)
            for message in messages
        ]
        filter_ = {"_id": {"$in": message_ids}}
        await self._message_collection.delete_many(filter_)

    async def get_newer_messages_of_kind(
        self, messages: List[TelegramMessage]
    ) -> List[TelegramMessage]:
        if not messages:
            return []
        filters_per_chat = [
            {
                "_id.c": message.chat.telegram_chat_id,
                "_id.m": {"$gt": message.telegram_message_id},
                "kind": message.kind,
            }
            for message in messages
        ]
        filter_ = {"$or": filters_per_chat}
        docs = await self._message_collection.find(filter_).to_list(None)
        return await self._convert_to_messages(docs)

    async def _convert_to_messages(self, docs: List[Document]) -> List[TelegramMessage]:
        chat_ids = [doc["_id"]["c"] for doc in docs]
        chats = {chat.telegram_chat_id: chat for chat in await self.find_chats_by_ids(chat_ids)}
        return [self._convert_to_message(doc, chats) for doc in docs]

    def _compose_message_id(self, telegram_chat_id: int, telegram_message_id: int) -> Any:
        return {"c": telegram_chat_id, "m": telegram_message_id}

    def _convert_to_message(
        self, doc: Document, chats: Mapping[int, TelegramChat]
    ) -> TelegramMessage:
        telegram_chat_id = doc["_id"]["c"]
        telegram_message_id = doc["_id"]["m"]
        return TelegramMessage(
            id=f"{telegram_chat_id}_{telegram_message_id}",
            telegram_bot_id=doc["telegram_bot_id"],
            chat=chats[telegram_chat_id],
            telegram_message_id=telegram_message_id,
            kind=TelegramMessageKind(doc["kind"]),
            agent_id=str(doc["agent_id"]) if "agent_id" in doc else None,
            customer_id=str(doc["customer_id"]) if "customer_id" in doc else None,
            conversation_id=str(doc["conversation_id"]) if "conversation_id" in doc else None,
            telegram_bot_username=doc.get("telegram_bot_username"),
        )
