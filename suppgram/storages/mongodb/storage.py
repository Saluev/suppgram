from typing import Any, List, Optional, Mapping, AsyncIterator

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from suppgram.entities import (
    Conversation,
    Message,
    WorkplaceIdentification,
    ConversationDiff,
    Customer,
    Tag,
    Agent,
    Workplace,
    AgentIdentification,
    AgentDiff,
    CustomerIdentification,
    CustomerDiff,
    Event,
)
from suppgram.errors import (
    AgentNotFound,
    WorkplaceNotFound,
    ConversationNotFound,
    TagAlreadyExists,
    ConversationAlreadyAssigned,
)
from suppgram.storage import Storage
from suppgram.storages.mongodb.collections import Collections, Document


class MongoDBStorage(Storage):
    """Implementation of [Storage][suppgram.storage.Storage] for MongoDB
    via [Motor](https://motor.readthedocs.io/) library."""

    def __init__(self, collections: Collections):
        """
        Parameters:
            collections: object storing collection names and conversion routines. Allows using custom
                         collection names, can be subclassed to customize BSON documents structure.
        """
        self._collections = collections

    async def create_or_update_customer(
        self, identification: CustomerIdentification, diff: Optional[CustomerDiff] = None
    ) -> Customer:
        filter_ = self._collections.make_customer_filter(identification)
        update = self._collections.make_customer_update(identification, diff)
        doc = await self._collections.customer_collection.find_one_and_update(
            filter_, update, upsert=identification.id is None, return_document=ReturnDocument.AFTER
        )
        if doc is None:
            raise ValueError("can't create customer with predefined ID")
        return self._collections.convert_to_customer(doc)

    async def find_customers_by_ids(self, customer_ids: List[Any]) -> List[Customer]:
        filter_ = self._collections.make_customers_filter(customer_ids)
        docs = await self._collections.customer_collection.find(filter_).to_list(None)
        return [self._collections.convert_to_customer(doc) for doc in docs]

    async def get_agent(self, identification: AgentIdentification) -> Agent:
        filter_ = self._collections.make_agent_filter(identification)
        doc = await self._collections.agent_collection.find_one(filter_)
        if doc is None:
            raise AgentNotFound(identification)
        return self._collections.convert_to_agent(doc)

    async def find_all_agents(self) -> AsyncIterator[Agent]:
        docs = self._collections.agent_collection.find({})
        async for doc in docs:
            yield self._collections.convert_to_agent(doc)

    async def create_or_update_agent(
        self, identification: AgentIdentification, diff: Optional[AgentDiff] = None
    ) -> Agent:
        try:
            return await self._update_agent(identification, diff, upsert=identification.id is None)
        except AgentNotFound:
            raise ValueError("can't create agent with predefined ID")

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
        if doc is None:
            raise AgentNotFound(identification)
        return self._collections.convert_to_agent(doc)

    async def get_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        filter_ = self._collections.make_agent_filter(identification)
        agent_doc = await self._collections.agent_collection.find_one(filter_)
        if agent_doc is None:
            raise WorkplaceNotFound(identification)
        return self._collections.convert_to_workplace(identification, agent_doc)

    async def find_workplaces_by_ids(self, workplace_ids: List[Any]) -> List[Workplace]:
        workplace_ids_set = set(workplace_ids)
        filter_ = self._collections.make_agents_filter_by_workplace_ids(workplace_ids)
        agent_docs = await self._collections.agent_collection.find(filter_).to_list(None)
        # TODO Agents here will be copied as many times as many of their
        #      workplaces are fetched. Might optimize a bit if got spare time.
        return [
            workplace
            for agent_doc in agent_docs
            for workplace in self._collections.convert_to_workplaces(agent_doc)
            if workplace.id in workplace_ids_set
        ]

    async def get_agent_workplaces(self, agent: Agent) -> List[Workplace]:
        filter_ = self._collections.make_agent_filter(agent.identification)
        agent_doc = await self._collections.agent_collection.find_one(filter_)
        if agent_doc is None:
            raise AgentNotFound(agent.identification)
        return self._collections.convert_to_workplaces(agent_doc)

    async def get_or_create_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        filter_ = self._collections.make_agent_filter(identification)
        agent_doc = await self._collections.agent_collection.find_one(filter_)
        if agent_doc is None:
            raise AgentNotFound(identification.to_agent_identification())
        if identification.id is None:
            agent_id = agent_doc["_id"]
            update = self._collections.convert_to_workspace_update(agent_id, identification)
            agent_doc = await self._collections.agent_collection.find_one_and_update(
                filter_, update, return_document=ReturnDocument.AFTER
            )
        return self._collections.convert_to_workplace(identification, agent_doc)

    async def create_tag(self, name: str, created_by: Agent) -> Tag:
        try:
            doc = self._collections.convert_to_tag_document(name, created_by)
            await self._collections.tag_collection.insert_one(doc)
            return self._collections.convert_to_tag(doc, {created_by.id: created_by})
        except DuplicateKeyError as exc:
            raise TagAlreadyExists(name) from exc

    async def find_all_tags(self) -> List[Tag]:
        docs = await self._collections.tag_collection.find({}).to_list(None)
        agent_ids = self._collections.extract_agent_ids(docs)
        filter_ = self._collections.make_agents_filter(agent_ids)
        agents = [
            self._collections.convert_to_agent(doc)
            for doc in await self._collections.agent_collection.find(filter_).to_list(None)
        ]
        agent_by_id = {agent.id: agent for agent in agents}
        return [self._collections.convert_to_tag(doc, agent_by_id) for doc in docs]

    async def get_or_create_conversation(self, customer: Customer) -> Conversation:
        filter_ = self._collections.make_conversation_filter_by_customer(customer)
        update = self._collections.make_conversation_update(customer=customer)
        doc = await self._collections.conversation_collection.find_one_and_update(
            filter_,
            update,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return await self._convert_single_conversation(doc)

    async def find_conversations_by_ids(
        self, conversation_ids: List[Any], with_messages: bool = False
    ) -> List[Conversation]:
        filter_ = self._collections.make_conversations_filter(conversation_ids)
        projection = self._collections.make_conversation_projection(with_messages=with_messages)
        docs = await self._collections.conversation_collection.find(
            filter_, projection=projection
        ).to_list(None)
        return await self._convert_multiple_conversations(docs)

    async def find_all_conversations(
        self, with_messages: bool = False
    ) -> AsyncIterator[Conversation]:
        projection = self._collections.make_conversation_projection(with_messages=with_messages)
        docs = self._collections.conversation_collection.find({}, projection=projection)
        batch: List[Document] = []
        async for doc in docs:
            batch.append(doc)
            if len(batch) >= 100:
                for conv in await self._convert_multiple_conversations(batch):
                    yield conv
                batch.clear()
        for conv in await self._convert_multiple_conversations(batch):
            yield conv

    async def count_all_conversations(self) -> int:
        return await self._collections.conversation_collection.count_documents({})

    async def update_conversation(
        self, id: Any, diff: ConversationDiff, unassigned_only: bool = False
    ):
        filter_ = self._collections.make_conversation_filter(id, unassigned_only=False)
        doc = await self._collections.conversation_collection.find_one(filter_)
        if doc is None:
            raise ConversationNotFound()

        workplaces: Mapping[Any, Workplace] = {}
        if (identification := diff.assigned_workplace_identification) is not None:
            workplace = await self.get_workplace(identification)
            workplaces = {workplace.id: workplace}
        filter_ = self._collections.make_conversation_filter(id, unassigned_only=unassigned_only)
        update = self._collections.make_conversation_update(diff=diff, workplaces=workplaces)
        result = await self._collections.conversation_collection.update_one(filter_, update)
        if result.matched_count == 0:
            raise ConversationAlreadyAssigned()

    async def get_agent_conversation(self, identification: WorkplaceIdentification) -> Conversation:
        workplace_id = identification.id
        if workplace_id is None:
            workplace = await self.get_workplace(identification)
            workplace_id = workplace.id
        filter_ = self._collections.make_workplace_conversation_filter(workplace_id)
        doc = await self._collections.conversation_collection.find_one(filter_)
        if doc is None:
            raise ConversationNotFound()
        return await self._convert_single_conversation(doc)

    async def find_customer_conversations(
        self, customer: Customer, with_messages: bool = False
    ) -> List[Conversation]:
        filter_ = self._collections.make_customer_conversations_filter(customer.id)
        projection = self._collections.make_conversation_projection(with_messages=with_messages)
        docs = await self._collections.conversation_collection.find(
            filter_, projection=projection
        ).to_list(None)
        return await self._convert_multiple_conversations(docs, customers={customer.id: customer})

    async def find_agent_conversations(
        self, agent: Agent, with_messages: bool = False
    ) -> List[Conversation]:
        filter_ = self._collections.make_agent_conversations_filter(agent.id)
        projection = self._collections.make_conversation_projection(with_messages=with_messages)
        docs = await self._collections.conversation_collection.find(
            filter_, projection=projection
        ).to_list(None)
        return await self._convert_multiple_conversations(docs)

    async def _convert_single_conversation(self, conv_doc: Document) -> Conversation:
        related_ids = self._collections.extract_conversation_related_ids(conv_doc)
        customer = await self.create_or_update_customer(related_ids.customer_identification)
        customers = {customer.id: customer}
        workplaces: Mapping[Any, Workplace] = {}
        if (workplace_identification := related_ids.assigned_workplace_identification) is not None:
            assigned_workplace = await self.get_workplace(workplace_identification)
            workplaces = {assigned_workplace.id: assigned_workplace}
        tags = {tag.id: tag for tag in await self.find_all_tags()}
        return self._collections.convert_to_conversation(conv_doc, customers, workplaces, tags)

    async def _convert_multiple_conversations(
        self, conv_docs: List[Document], customers: Mapping[Any, Customer] = {}
    ) -> List[Conversation]:
        related_ids = [self._collections.extract_conversation_related_ids(doc) for doc in conv_docs]
        if not customers:
            customer_ids = [r.customer_id for r in related_ids]
            customers = {
                customer.id: customer for customer in await self.find_customers_by_ids(customer_ids)
            }
        workplace_ids = [
            r.assigned_workplace_id for r in related_ids if r.assigned_workplace_id is not None
        ]
        workplaces = {
            workplace.id: workplace
            for workplace in await self.find_workplaces_by_ids(workplace_ids)
        }
        tags = {tag.id: tag for tag in await self.find_all_tags()}
        return [
            self._collections.convert_to_conversation(doc, customers, workplaces, tags)
            for doc in conv_docs
        ]

    async def save_message(self, conversation: Conversation, message: Message):
        filter_ = self._collections.make_conversation_filter(conversation.id, unassigned_only=False)
        update = self._collections.make_message_update(message)
        result = await self._collections.conversation_collection.update_one(filter_, update)
        if result.matched_count == 0:
            raise ConversationNotFound()

    async def save_event(self, event: Event):
        doc = self._collections.convert_to_event_document(event)
        await self._collections.event_collection.insert_one(doc)

    async def find_all_events(self) -> AsyncIterator[Event]:
        docs = self._collections.event_collection.find({})
        async for doc in docs:
            yield self._collections.convert_to_event(doc)

    async def count_all_events(self) -> int:
        return await self._collections.event_collection.count_documents({})
