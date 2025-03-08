from datetime import timezone, datetime
from typing import (
    Any,
    Mapping,
    Optional,
    List,
    Union,
    Set,
    Iterable,
    NamedTuple,
    Dict,
)

from bson import ObjectId, CodecOptions, UuidRepresentation
from motor.core import AgnosticDatabase

from suppgram.containers import UnavailableList
from suppgram.entities import (
    Agent,
    AgentIdentification,
    AgentDiff,
    WorkplaceIdentification,
    Workplace,
    Tag,
    CustomerIdentification,
    CustomerDiff,
    Customer,
    FINAL_STATES,
    ConversationState,
    Conversation,
    Message,
    MessageKind,
    ConversationDiff,
    SetNone,
    Event,
    MessageMediaKind,
    EventKind,
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

    @property
    def assigned_workplace_identification(self) -> Optional[WorkplaceIdentification]:
        if self.assigned_workplace_id is None:
            return None
        return WorkplaceIdentification(id=self.assigned_workplace_id)


class Collections:
    """Abstraction layer over MongoDB database and collection names and BSON documents structure."""

    def __init__(
        self,
        database: AgnosticDatabase,
        customer_collection_name: str = "suppgram_customers",
        agent_collection_name: str = "suppgram_agents",
        conversation_collection_name: str = "suppgram_conversations",
        tag_collection_name: str = "suppgram_tags",
        event_collection_name: str = "suppgram_events",
        codec_options: CodecOptions = CodecOptions(
            tz_aware=True, tzinfo=timezone.utc, uuid_representation=UuidRepresentation.STANDARD
        ),
    ):
        """
        Parameters:
            database: asyncio-compatible Motor MongoDB database to store data in
            customer_collection_name: name of MongoDB collection to store customers in
            agent_collection_name: name of MongoDB collection to store agents and workplaces in
            conversation_collection_name: name of MongoDB collection to store conversations and messages in
            tag_collection_name: name of MongoDB collection to store tags in
        """
        self.customer_collection = database.get_collection(customer_collection_name, codec_options)
        self.agent_collection = database.get_collection(agent_collection_name, codec_options)
        # Workplaces are stored within agents.
        self.conversation_collection = database.get_collection(
            conversation_collection_name, codec_options
        )
        # Messages are stored within conversations.
        self.tag_collection = database.get_collection(tag_collection_name, codec_options)
        self.event_collection = database.get_collection(event_collection_name, codec_options)

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

    def make_customers_filter(self, ids: Iterable[Any]) -> Document:
        return {"_id": {"$in": [ObjectId(id) for id in ids]}}

    def convert_to_customer(self, doc: Document) -> Customer:
        return Customer(
            id=str(doc["_id"]),
            telegram_user_id=doc.get("telegram_user_id"),
            telegram_first_name=doc.get("telegram_first_name"),
            telegram_last_name=doc.get("telegram_last_name"),
            telegram_username=doc.get("telegram_username"),
            shell_uuid=doc.get("shell_uuid"),  # MongoDB supports UUIDs
            pubnub_user_id=doc.get("pubnub_user_id"),
            pubnub_channel_id=doc.get("pubnub_channel_id"),
        )

    def make_customer_update(
        self, identification: CustomerIdentification, diff: Optional[CustomerDiff]
    ) -> Document:
        result: Dict[str, Any] = {}
        if identification.telegram_user_id is not None:
            result["telegram_user_id"] = identification.telegram_user_id
        if identification.pubnub_user_id is not None:
            result["pubnub_user_id"] = identification.pubnub_user_id
            result["pubnub_channel_id"] = identification.pubnub_channel_id
        if identification.shell_uuid is not None:
            result["shell_uuid"] = identification.shell_uuid  # MongoDB supports UUIDs
        if diff is None:
            return {"$set": result}
        if diff.telegram_first_name is not None:
            result["telegram_first_name"] = diff.telegram_first_name
        if diff.telegram_last_name is not None:
            result["telegram_last_name"] = diff.telegram_last_name
        if diff.telegram_username is not None:
            result["telegram_username"] = diff.telegram_username
        return {"$set": result}

    def make_agent_filter(
        self, identification: Union[AgentIdentification, WorkplaceIdentification]
    ) -> Document:
        if isinstance(identification, AgentIdentification) and identification.id is not None:
            return {"_id": ObjectId(identification.id)}
        if isinstance(identification, WorkplaceIdentification) and identification.id is not None:
            return {"workplaces.id": identification.id}
        if identification.telegram_user_id is not None:
            return {"telegram_user_id": identification.telegram_user_id}
        raise AgentEmptyIdentification(
            identification.to_agent_identification()
            if isinstance(identification, WorkplaceIdentification)
            else identification
        )

    def make_agents_filter(self, agent_ids: Iterable[Any]) -> Document:
        return {"_id": {"$in": [ObjectId(id) for id in agent_ids]}}

    def make_agents_filter_by_workplace_ids(self, workplace_ids: Iterable[Any]) -> Document:
        return {"workplaces.id": {"$in": list(workplace_ids)}}

    def convert_to_agent(self, agent_doc: Document) -> Agent:
        return Agent(
            id=str(agent_doc["_id"]),
            deactivated=bool(agent_doc.get("deactivated")),
            telegram_user_id=agent_doc.get("telegram_user_id"),
            telegram_first_name=agent_doc.get("telegram_first_name"),
            telegram_last_name=agent_doc.get("telegram_last_name"),
            telegram_username=agent_doc.get("telegram_username"),
        )

    def convert_to_agent_update(
        self, identification: AgentIdentification, diff: Optional[AgentDiff]
    ) -> Document:
        result: Dict[str, Any] = {"$set": {}, "$setOnInsert": {"workplaces": []}}
        if identification.telegram_user_id is not None:
            result["$set"]["telegram_user_id"] = identification.telegram_user_id
        if diff is None:
            return result
        if diff.deactivated is not None:
            result["$set"]["deactivated"] = diff.deactivated
        if diff.telegram_first_name is not None:
            result["$set"]["telegram_first_name"] = diff.telegram_first_name
        if diff.telegram_last_name is not None:
            result["$set"]["telegram_last_name"] = diff.telegram_last_name
        if diff.telegram_username is not None:
            result["$set"]["telegram_username"] = diff.telegram_username
        return result

    def convert_to_workplace(
        self, identification: WorkplaceIdentification, agent_doc: Document
    ) -> Workplace:
        workplace_subdocs = agent_doc["workplaces"]
        if identification.id is not None:

            def predicate(subdoc: Document):
                return subdoc["id"] == identification.id

        elif identification.telegram_bot_id is not None:

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

    def convert_to_workplaces(self, agent_doc: Document) -> List[Workplace]:
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
        result: Dict[str, Any] = {}
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

    def convert_to_tag(self, doc: Document, agents: Mapping[Any, Agent]) -> Tag:
        agent = agents[str(doc["created_by"])]
        return Tag(
            id=doc["_id"],
            name=doc["_id"],
            created_at_utc=doc["created_at_utc"],
            created_by=agent,
        )

    def make_conversation_filter_by_customer(self, customer: Customer) -> Document:
        return {"customer_id": ObjectId(customer.id), "state": {"$nin": FINAL_STATES}}

    def make_conversation_filter(self, id: Any, unassigned_only: bool) -> Document:
        result: Dict[str, Any] = {"_id": ObjectId(id)}
        if unassigned_only:
            result["assigned_workplace_id"] = None
        return result

    def make_conversations_filter(self, ids: Iterable[Any]) -> Document:
        return {"_id": {"$in": [ObjectId(id) for id in ids]}}

    def make_customer_conversations_filter(self, customer_id: Any) -> Document:
        return {"customer_id": ObjectId(customer_id)}

    def make_agent_conversations_filter(self, agent_id: Any) -> Document:
        return {"assigned_agent_id": ObjectId(agent_id)}

    def make_workplace_conversation_filter(self, workplace_id: Any) -> Document:
        return {"assigned_workplace_id": workplace_id}

    def make_conversation_update(
        self,
        customer: Optional[Customer] = None,
        diff: Optional[ConversationDiff] = None,
        workplaces: Mapping[Any, Workplace] = {},
    ) -> Document:
        result: Dict[str, Any] = {"$set": {}, "$setOnInsert": {}}
        if customer is not None:
            result["$setOnInsert"].update(
                {
                    "state": ConversationState.NEW,
                    "customer_id": ObjectId(customer.id),
                    "tag_ids": [],
                    "messages": [],
                }
            )
        if diff is not None:
            if diff.state is not None:
                result["$set"]["state"] = diff.state

            if diff.assigned_workplace_id is SetNone:
                result["$unset"] = {"assigned_agent_id": True, "assigned_workplace_id": True}
            elif diff.assigned_workplace_id is not None:
                result["$set"].update(
                    {
                        "assigned_agent_id": ObjectId(
                            workplaces[diff.assigned_workplace_id].agent.id
                        ),
                        "assigned_workplace_id": diff.assigned_workplace_id,
                    }
                )

            if diff.added_tags:
                result["$addToSet"] = {"tag_ids": {"$each": [tag.id for tag in diff.added_tags]}}

            if diff.removed_tags:
                result["$pull"] = {"tag_ids": {"$in": [tag.id for tag in diff.removed_tags]}}

            # TODO probably should allow adding and removing at the same time, which MongoDB forbids

            if diff.customer_rating is not None:
                result["$set"]["customer_rating"] = diff.customer_rating

        return result

    def extract_conversation_related_ids(self, conv_doc: Document) -> ConversationRelatedIDs:
        assigned_agent_id = conv_doc.get("assigned_agent_id")
        return ConversationRelatedIDs(
            customer_id=str(conv_doc["customer_id"]),
            assigned_agent_id=str(assigned_agent_id) if assigned_agent_id is not None else None,
            assigned_workplace_id=conv_doc.get("assigned_workplace_id"),
        )

    def make_conversation_projection(self, with_messages: bool) -> Document:
        if not with_messages:
            return {"messages": False}
        return {}

    def convert_to_conversation(
        self,
        doc: Document,
        customers: Mapping[Any, Customer],
        workplaces: Mapping[Any, Workplace],
        tags: Mapping[Any, Tag],
    ) -> Conversation:
        assigned_workplace_id = doc.get("assigned_workplace_id")
        assigned_workplace = (
            workplaces[str(assigned_workplace_id)] if assigned_workplace_id is not None else None
        )
        assigned_agent = assigned_workplace.agent if assigned_workplace is not None else None
        return Conversation(
            id=str(doc["_id"]),
            state=ConversationState(doc["state"]),
            customer=customers[str(doc["customer_id"])],
            tags=[tags[tag_id] for tag_id in doc["tag_ids"]],
            assigned_agent=assigned_agent,
            assigned_workplace=assigned_workplace,
            messages=[
                Message(
                    kind=MessageKind(message_doc["kind"]),
                    time_utc=message_doc["time_utc"],
                    text=message_doc.get("text"),
                    image=message_doc.get("image"),
                )
                for message_doc in doc["messages"]
            ]
            if "messages" in doc
            else UnavailableList[Message](),
            customer_rating=doc.get("customer_rating"),
        )

    def make_message_update(self, message: Message) -> Document:
        return {
            "$push": {
                "messages": {
                    "kind": message.kind,
                    "time_utc": message.time_utc,
                    **_maybe("text", message.text),
                    **_maybe("image", message.image),
                }
            }
        }

    def convert_to_event_document(self, event: Event) -> Document:
        doc = {
            "kind": event.kind,
            "time_utc": event.time_utc,
            "agent_id": ObjectId(event.agent_id),
            "conversation_id": ObjectId(event.conversation_id),
            "customer_id": ObjectId(event.customer_id),
            "message_kind": event.message_kind,
            "message_media_kind": event.message_media_kind,
            "tag_id": event.tag_id,
            "workplace_id": event.workplace_id,
        }
        return {k: v for k, v in doc.items() if v is not None}

    def convert_to_event(self, doc: Document) -> Event:
        return Event(
            kind=EventKind(doc["kind"]),
            time_utc=doc["time_utc"],
            agent_id=str(doc["agent_id"]) if "agent_id" in doc else None,
            conversation_id=str(doc["conversation_id"]) if "conversation_id" in doc else None,
            customer_id=str(doc["customer_id"]) if "customer_id" in doc else None,
            message_kind=MessageKind(doc["message_kind"]) if "message_kind" in doc else None,
            message_media_kind=MessageMediaKind(doc["message_media_kind"])
            if "message_media_kind" in doc
            else None,
            tag_id=doc.get("tag_id"),
            workplace_id=doc.get("workplace_id"),
        )


def _maybe(key: str, value: Any) -> dict[str, Any]:
    return {key: value} if value else {}
