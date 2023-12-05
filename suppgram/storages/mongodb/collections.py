from datetime import timezone, datetime
from typing import Any, Mapping, Optional, List, Union, MutableMapping, Set, Iterable, NamedTuple

from bson import ObjectId, CodecOptions
from motor.core import AgnosticDatabase

from suppgram.entities import (
    Agent,
    AgentIdentification,
    AgentDiff,
    WorkplaceIdentification,
    Workplace,
    ConversationTag,
    CustomerIdentification,
    CustomerDiff,
    Customer,
    FINAL_STATES,
    ConversationState,
)
from suppgram.errors import (
    AgentEmptyIdentification,
    WorkplaceEmptyIdentification,
    WorkplaceNotFound,
    CustomerEmptyIdentification,
)

Document = Mapping[str, Any]


class ConversationRelatedIDs(NamedTuple):
    customer_id: Any
    assigned_agent_id: Any
    assigned_workplace_id: Any

    @property
    def customer_identification(self) -> CustomerIdentification:
        return CustomerIdentification(id=self.customer_id)


class Collections:
    def __init__(self, database: AgnosticDatabase):
        codec_options: CodecOptions = CodecOptions(tz_aware=True, tzinfo=timezone.utc)
        self.customer_collection = database.get_collection("suppgram_customers", codec_options)
        self.agent_collection = database.get_collection("suppgram_agents", codec_options)
        # Workplaces are stored within agents.
        self.conversation_collection = database.get_collection(
            "suppgram_conversations", codec_options
        )
        # Messages are stored within conversations.
        self.conversation_tag_collection = database.get_collection(
            "suppgram_conversation_tags", codec_options
        )

    def make_customer_filter(self, identification: CustomerIdentification) -> Document:
        if identification.id is not None:
            return {"_id": ObjectId(identification.id)}
        if identification.telegram_user_id is not None:
            return {"telegram_user_id": identification.telegram_user_id}
        if identification.pubnub_user_id is not None:
            return {
                "pubnub_user_id": identification.pubnub_user_id,
                "pubnub_channel_id": identification.pubnub_channel_id,
            }
        if identification.shell_uuid is not None:
            return {"shell_uuid": identification.shell_uuid}  # MongoDB supports UUIDs
        raise CustomerEmptyIdentification(identification)

    def convert_to_customer(self, doc: Document) -> Customer:
        return Customer(
            id=str(doc["_id"]),
            telegram_user_id=doc.get("telegram_user_id"),
            telegram_first_name=doc.get("telegram_first_name"),
            telegram_last_name=doc.get("telegram_last_name"),
            shell_uuid=doc.get("shell_uuid"),  # MongoDB supports UUIDs
            pubnub_user_id=doc.get("pubnub_user_id"),
            pubnub_channel_id=doc.get("pubnub_channel_id"),
        )

    def make_customer_update(
        self, identification: CustomerIdentification, diff: Optional[CustomerDiff]
    ) -> Document:
        result: MutableMapping[str, Any] = {}
        if identification.telegram_user_id is not None:
            result["telegram_user_id"] = identification.telegram_user_id
        if identification.pubnub_user_id is not None:
            result["pubnub_user_id"] = identification.pubnub_user_id
            result["pubnub_channel_id"] = identification.pubnub_channel_id
        if identification.shell_uuid is not None:
            result["shell_uuid"] = identification.shell_uuid  # MongoDB supports UUIDs
        if diff is None:
            return result
        if diff.telegram_first_name is not None:
            result["telegram_first_name"] = diff.telegram_first_name
        if diff.telegram_last_name is not None:
            result["telegram_last_name"] = diff.telegram_last_name
        if diff.telegram_username is not None:
            result["telegram_username"] = diff.telegram_username
        return result

    def make_agent_filter(
        self, identification: Union[AgentIdentification, WorkplaceIdentification]
    ) -> Document:
        if isinstance(identification, AgentIdentification) and identification.id is not None:
            return {"_id": ObjectId(identification.id)}
        if identification.telegram_user_id is not None:
            return {"telegram_user_id": identification.telegram_user_id}
        raise AgentEmptyIdentification(
            identification.to_agent_identification()
            if isinstance(identification, WorkplaceIdentification)
            else identification
        )

    def make_agents_filter(self, ids: Iterable[Any]) -> Document:
        return {"_id": {"$in": [ObjectId(id) for id in ids]}}

    def convert_to_agent(self, agent_doc: Document) -> Agent:
        return Agent(
            id=str(agent_doc["_id"]),
            telegram_user_id=agent_doc.get("telegram_user_id"),
            telegram_first_name=agent_doc.get("telegram_first_name"),
            telegram_last_name=agent_doc.get("telegram_last_name"),
            telegram_username=agent_doc.get("telegram_username"),
        )

    def convert_to_agent_update(
        self, identification: AgentIdentification, diff: Optional[AgentDiff]
    ) -> Document:
        result: MutableMapping[str, Any] = {}
        if identification.telegram_user_id is not None:
            result["telegram_user_id"] = identification.telegram_user_id
        if diff is None:
            return result
        if diff.telegram_first_name is not None:
            result["telegram_first_name"] = diff.telegram_first_name
        if diff.telegram_last_name is not None:
            result["telegram_last_name"] = diff.telegram_last_name
        if diff.telegram_username is not None:
            result["telegram_username"] = diff.telegram_username
        return {"$set": result}

    def convert_to_workplace(
        self, identification: WorkplaceIdentification, agent_doc: Document
    ) -> Workplace:
        workplace_subdocs = agent_doc["workplaces"]
        if identification.telegram_bot_id is not None:

            def predicate(subdoc: Document):
                return subdoc["telegram_bot_id"] == identification.telegram_bot_id

        else:
            raise WorkplaceEmptyIdentification(identification)
        try:
            workplace_doc = next(
                workplace_doc for workplace_doc in workplace_subdocs if predicate(workplace_doc)
            )
        except StopIteration:
            raise WorkplaceNotFound(identification)
        return self._convert_from_workplace_subdocument(agent_doc, workplace_doc)

    def convert_to_workspaces(self, agent_doc: Document) -> List[Workplace]:
        workplace_subdocs = agent_doc["workplaces"]
        return [
            self._convert_from_workplace_subdocument(agent_doc, workplace_subdoc)
            for workplace_subdoc in workplace_subdocs
        ]

    def _convert_from_workplace_subdocument(
        self, agent_doc: Document, workplace_doc: Document
    ) -> Workplace:
        return Workplace(
            id=str(workplace_doc["id"]),
            telegram_user_id=agent_doc.get("telegram_user_id"),
            telegram_bot_id=workplace_doc["telegram_bot_id"],
            agent=self.convert_to_agent(agent_doc),
        )

    def convert_to_workspace_update(
        self, agent_id: Any, identification: WorkplaceIdentification
    ) -> Document:
        result: MutableMapping[str, Any] = {}
        if identification.telegram_bot_id is not None:
            result["id"] = f"{agent_id}_{identification.telegram_bot_id}"
            result["telegram_bot_id"] = identification.telegram_bot_id
        else:
            raise WorkplaceEmptyIdentification(identification)
        # WARNING: once we add auxiliary fields to Workplace, $addToSet will stop being a viable solution.
        # Maybe we'll have to store metadata in a parallel array.
        return {"$addToSet": {"workplaces": result}}

    def convert_to_tag_document(self, name: str, created_by: Agent) -> Document:
        return {
            "_id": name,
            "created_at_utc": datetime.now(timezone.utc),
            "created_by": ObjectId(created_by.id),
        }

    def extract_agent_ids(self, tag_docs: List[Document]) -> Set[ObjectId]:
        return {tag_doc["created_by"] for tag_doc in tag_docs}

    def convert_to_tag(self, doc: Document, agents: Mapping[Any, Agent]) -> ConversationTag:
        agent = agents[str(doc["created_by"])]
        return ConversationTag(
            id=doc["_id"],
            name=doc["name"],
            created_at_utc=doc["created_at_utc"],
            created_by=agent,
        )

    def make_conversation_filter(self, customer: Customer) -> Document:
        return {"customer_id": ObjectId(customer.id), "state": {"$nin": FINAL_STATES}}

    def make_conversation_update(self, customer: Customer) -> Document:
        return {
            "$setOnInsert": {
                "state": ConversationState.NEW,
                "customer_id": ObjectId(customer.id),
                "tag_ids": [],
                "messages": [],
            }
        }

    def extract_conversation_related_ids(self, conv_doc: Document) -> ConversationRelatedIDs:
        return ConversationRelatedIDs(
            customer_id=str(conv_doc["customer_id"]),
            assigned_agent_id=str(conv_doc["assigned_agent_id"])
            if "assigned_agent_id" in conv_doc
            else None,
            assigned_workplace_id=conv_doc.get("assigned_workplace_id"),
        )

    def make_conversations_filter(self, ids: Iterable[Any]) -> Document:
        return {"_id": {"$in": [ObjectId(id) for id in ids]}}
