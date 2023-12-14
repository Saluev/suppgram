from datetime import timezone
from typing import List, Optional, Any, Iterable, Mapping, MutableMapping

from bson import CodecOptions, ObjectId
from motor.core import AgnosticDatabase
from pymongo import ReturnDocument

from suppgram.frontends.telegram.interfaces import (
    TelegramStorage,
    TelegramMessage,
    TelegramMessageKind,
    TelegramGroup,
    TelegramGroupRole,
)
from suppgram.storages.mongodb.collections import Document


class MongoDBTelegramBridge(TelegramStorage):
    """Implementation of [Storage][suppgram.storage.Storage] for MongoDB
    via [Motor](https://motor.readthedocs.io/) library."""

    def __init__(
        self,
        database: AgnosticDatabase,
        group_collection_name: str = "suppgram_telegram_groups",
        messages_collection_name: str = "suppgram_telegram_messages",
    ):
        """
        Parameters:
            database: asyncio-compatible Motor MongoDB database to store data in
            group_collection_name: name of MongoDB collection to store data on Telegram groups in
            messages_collection_name: name of MongoDB collection to store references to Telegram messages in
        """
        codec_options: CodecOptions = CodecOptions(tz_aware=True, tzinfo=timezone.utc)
        self._group_collection = database.get_collection(group_collection_name, codec_options)
        self._message_collection = database.get_collection(messages_collection_name, codec_options)

    async def get_group(self, telegram_chat_id: int) -> TelegramGroup:
        filter_ = self._make_group_filter(telegram_chat_id)
        doc = await self._group_collection.find_one(filter_)
        if doc is None:
            raise ValueError(f"couldn't find Telegram group {telegram_chat_id}")
        return self._convert_to_group(doc)

    async def find_groups_by_ids(self, telegram_chat_ids: List[int]) -> List[TelegramGroup]:
        filter_ = self._make_groups_filter(telegram_chat_ids)
        docs = await self._group_collection.find(filter_).to_list(None)
        return [self._convert_to_group(doc) for doc in docs]

    async def create_or_update_group(self, telegram_chat_id: int) -> TelegramGroup:
        filter_ = self._make_group_filter(telegram_chat_id)
        update = self._make_group_update()
        doc = await self._group_collection.find_one_and_update(
            filter_, update, upsert=True, return_document=ReturnDocument.AFTER
        )
        return self._convert_to_group(doc)

    async def add_group_roles(self, telegram_chat_id: int, *roles: TelegramGroupRole):
        filter_ = self._make_group_filter(telegram_chat_id)
        update = self._make_group_roles_update(roles)
        await self._group_collection.update_one(filter_, update)

    async def get_groups_by_role(self, role: TelegramGroupRole) -> List[TelegramGroup]:
        filter_ = self._make_group_filter_by_role(role)
        docs = await self._group_collection.find(filter_).to_list(None)
        return [self._convert_to_group(doc) for doc in docs]

    def _make_group_filter(self, telegram_chat_id: int) -> Document:
        return {"_id": telegram_chat_id}

    def _make_groups_filter(self, telegram_chat_ids: List[int]) -> Document:
        return {"_id": {"$in": telegram_chat_ids}}

    def _make_group_filter_by_role(self, role: TelegramGroupRole) -> Document:
        return {"roles": role.value}

    def _make_group_update(self) -> Document:
        return {"$setOnInsert": {"roles": []}}

    def _make_group_roles_update(self, roles: Iterable[TelegramGroupRole]) -> Document:
        return {"$addToSet": {"roles": {"$each": [role.value for role in roles]}}}

    def _convert_to_group(self, doc: Document) -> TelegramGroup:
        return TelegramGroup(
            telegram_chat_id=doc["_id"],
            roles=frozenset(TelegramGroupRole(role) for role in doc.get("roles", [])),
        )

    async def insert_message(
        self,
        telegram_bot_id: int,
        group: TelegramGroup,
        telegram_message_id: int,
        kind: TelegramMessageKind,
        agent_id: Optional[Any] = None,
        customer_id: Optional[Any] = None,
        conversation_id: Optional[Any] = None,
        telegram_bot_username: Optional[str] = None,
    ) -> TelegramMessage:
        doc = {
            "_id": self._compose_message_id(group.telegram_chat_id, telegram_message_id),
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
        return self._convert_to_message(doc, {group.telegram_chat_id: group})

    async def get_message(self, group: TelegramGroup, telegram_message_id: int) -> TelegramMessage:
        filter_ = {"_id": self._compose_message_id(group.telegram_chat_id, telegram_message_id)}
        doc = await self._message_collection.find_one(filter_)
        if doc is None:
            raise ValueError(
                f"couldn't find Telegram message {telegram_message_id} in group {group.telegram_chat_id}"
            )
        return self._convert_to_message(doc, groups={group.telegram_chat_id: group})

    async def get_messages(
        self,
        kind: TelegramMessageKind,
        agent_id: Optional[Any] = None,
        conversation_id: Optional[Any] = None,
        telegram_bot_username: Optional[str] = None,
    ) -> List[TelegramMessage]:
        filter_: MutableMapping[str, Any] = {"kind": kind}
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
            self._compose_message_id(message.group.telegram_chat_id, message.telegram_message_id)
            for message in messages
        ]
        filter_ = {"_id": {"$in": message_ids}}
        await self._message_collection.delete_many(filter_)

    async def get_newer_messages_of_kind(
        self, messages: List[TelegramMessage]
    ) -> List[TelegramMessage]:
        if not messages:
            return []
        filters_per_group = [
            {
                "_id.c": message.group.telegram_chat_id,
                "_id.m": {"$gt": message.telegram_message_id},
            }
            for message in messages
        ]
        filter_ = {"$or": filters_per_group}
        docs = await self._message_collection.find(filter_).to_list(None)
        return await self._convert_to_messages(docs)

    async def _convert_to_messages(self, docs: List[Document]) -> List[TelegramMessage]:
        group_ids = [doc["_id"]["c"] for doc in docs]
        groups = {
            group.telegram_chat_id: group for group in await self.find_groups_by_ids(group_ids)
        }
        return [self._convert_to_message(doc, groups) for doc in docs]

    def _compose_message_id(self, telegram_chat_id: int, telegram_message_id: int) -> Any:
        return {"c": telegram_chat_id, "m": telegram_message_id}

    def _convert_to_message(
        self, doc: Document, groups: Mapping[int, TelegramGroup]
    ) -> TelegramMessage:
        telegram_chat_id = doc["_id"]["c"]
        telegram_message_id = doc["_id"]["m"]
        return TelegramMessage(
            id=f"{telegram_chat_id}_{telegram_message_id}",
            telegram_bot_id=doc["telegram_bot_id"],
            group=groups[telegram_chat_id],
            telegram_message_id=telegram_message_id,
            kind=TelegramMessageKind(doc["kind"]),
            customer_id=str(doc["customer_id"]) if "customer_id" in doc else None,
            conversation_id=str(doc["conversation_id"]) if "conversation_id" in doc else None,
            telegram_bot_username=doc.get("telegram_bot_username"),
        )
