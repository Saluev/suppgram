from typing import Any, List, Optional

from motor.core import AgnosticClient
from pymongo import ReturnDocument

from suppgram.entities import (
    Conversation,
    Message,
    WorkplaceIdentification,
    ConversationDiff,
    Customer,
    ConversationTag,
    Agent,
    Workplace,
    AgentIdentification,
    AgentDiff,
    CustomerIdentification,
    CustomerDiff,
)
from suppgram.errors import AgentNotFound, WorkplaceNotFound
from suppgram.storage import Storage
from suppgram.storages.mongodb.collections import Collections


class MongoDBStorage(Storage):
    def __init__(self, client: AgnosticClient, collections: Collections):
        self._client = client
        self._collections = collections

    async def create_or_update_customer(
        self, identification: CustomerIdentification, diff: Optional[CustomerDiff] = None
    ) -> Customer:
        filter_ = self._collections.make_customer_filter(identification)
        update = self._collections.make_customer_update(identification, diff)
        doc = await self._collections.customer_collection.find_one_and_update(
            filter_, update, upsert=True, return_document=ReturnDocument.AFTER
        )
        return self._collections.convert_to_customer(doc)

    async def get_agent(self, identification: AgentIdentification) -> Agent:
        filter_ = self._collections.make_agent_filter(identification)
        doc = await self._collections.agent_collection.find_one(filter_)
        if doc is None:
            raise AgentNotFound(identification)
        return self._collections.convert_to_agent(doc)

    async def create_or_update_agent(
        self, identification: AgentIdentification, diff: Optional[AgentDiff] = None
    ) -> Agent:
        return await self._update_agent(identification, diff, upsert=True)

    async def update_agent(self, identification: AgentIdentification, diff: AgentDiff) -> Agent:
        return await self._update_agent(identification, diff, upsert=False)

    async def _update_agent(
        self, identification: AgentIdentification, diff: Optional[AgentDiff], upsert: bool
    ) -> Agent:
        filter_ = self._collections.make_agent_filter(identification)
        update = self._collections.convert_to_agent_update(identification, diff)
        doc = await self._collections.agent_collection.find_one_and_update(
            filter_, update, upsert=upsert, return_document=ReturnDocument.AFTER
        )
        return self._collections.convert_to_agent(doc)

    async def get_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        filter_ = self._collections.make_agent_filter(identification)
        doc = await self._collections.agent_collection.find_one(filter_)
        if doc is None:
            raise WorkplaceNotFound(identification)
        return self._collections.convert_to_workplace(identification, doc)

    async def get_agent_workplaces(self, agent: Agent) -> List[Workplace]:
        filter_ = self._collections.make_agent_filter(agent.identification)
        doc = await self._collections.agent_collection.find_one(filter_)
        if doc is None:
            raise AgentNotFound(agent.identification)
        return self._collections.convert_to_workspaces(doc)

    async def get_or_create_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        filter_ = self._collections.make_agent_filter(identification)
        doc = await self._collections.agent_collection.find_one(filter_)
        if doc is None:
            raise AgentNotFound(identification.to_agent_identification())
        agent_id = doc["_id"]
        update = self._collections.convert_to_workspace_update(agent_id, identification)
        doc = await self._collections.agent_collection.find_one_and_update(
            filter_, update, return_document=ReturnDocument.AFTER
        )
        return self._collections.convert_to_workplace(identification, doc)

    async def create_tag(self, name: str, created_by: Agent):
        doc = self._collections.convert_to_tag_document(name, created_by)
        await self._collections.conversation_tag_collection.insert_one(doc)

    async def find_all_tags(self) -> List[ConversationTag]:
        docs = await self._collections.conversation_tag_collection.find({}).to_list(None)
        agent_ids = self._collections.extract_agent_ids(docs)
        filter_ = self._collections.make_agents_filter(agent_ids)
        agents = [
            self._collections.convert_to_agent(doc)
            for doc in await self._collections.agent_collection.find(filter_).to_list(None)
        ]
        agent_by_id = {agent.id: agent for agent in agents}
        return [self._collections.convert_to_tag(doc, agent_by_id) for doc in docs]

    async def get_or_create_conversation(self, customer: Customer) -> Conversation:
        filter_ = self._collections.make_conversation_filter(customer)
        update = self._collections.make_conversation_update(customer)
        doc = await self._collections.conversation_collection.find_one_and_update(
            filter_, update, upsert=True, return_document=ReturnDocument.AFTER
        )
        related_ids = self._collections.extract_conversation_related_ids(doc)
        customer = await self.create_or_update_customer(related_ids.customer_identification)
        assigned_workplace: Optional[Workplace] = None
        if related_ids.assigned_workplace_id is not None:
            pass  # TODO
        raise NotImplementedError
        _ = assigned_workplace

    async def find_conversations_by_ids(
        self, conversation_ids: List[Any], with_messages: bool = False
    ) -> List[Conversation]:
        raise NotImplementedError

    async def update_conversation(
        self, id: Any, diff: ConversationDiff, unassigned_only: bool = False
    ):
        raise NotImplementedError

    async def get_agent_conversation(self, identification: WorkplaceIdentification) -> Conversation:
        raise NotImplementedError

    async def save_message(self, conversation: Conversation, message: Message):
        raise NotImplementedError
