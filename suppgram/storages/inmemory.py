from dataclasses import replace
from datetime import datetime, timezone
from typing import List, Any, Optional, Dict, AsyncIterator
from uuid import uuid4

from suppgram.containers import UnavailableList
from suppgram.entities import (
    Conversation,
    Message,
    Agent,
    Customer,
    WorkplaceIdentification,
    ConversationDiff,
    Tag,
    Workplace,
    AgentIdentification,
    AgentDiff,
    CustomerIdentification,
    CustomerDiff,
    ConversationState,
    SetNone,
    Event,
)
from suppgram.errors import (
    AgentNotFound,
    TagAlreadyExists,
    WorkplaceNotFound,
    ConversationNotFound,
    ConversationAlreadyAssigned,
)
from suppgram.storage import Storage


class InMemoryStorage(Storage):
    """In-memory implementation of [Storage][suppgram.storage.Storage] used in tests."""

    def __init__(self) -> None:
        self.customers: List[Customer] = []
        self.agents: List[Agent] = []
        self.workplaces: List[Workplace] = []
        self.tags: List[Tag] = []
        self.conversations: List[Conversation] = []
        self.events: List[Event] = []

    async def create_or_update_customer(
        self, identification: CustomerIdentification, diff: Optional[CustomerDiff] = None
    ) -> Customer:
        try:
            idx = next(
                i for i, c in enumerate(self.customers) if self._match_customer(identification, c)
            )
            customer = self.customers.pop(idx)
        except StopIteration:
            customer = self._construct_customer(identification)
        customer = self._update_customer(customer, diff)
        self.customers.append(customer)
        return customer

    async def get_agent(self, identification: AgentIdentification) -> Agent:
        try:
            return next(a for a in self.agents if self._match_agent(identification, a))
        except StopIteration:
            raise AgentNotFound(identification)

    async def find_all_agents(self) -> AsyncIterator[Agent]:
        for agent in self.agents:
            yield agent

    async def create_or_update_agent(
        self, identification: AgentIdentification, diff: Optional[AgentDiff] = None
    ) -> Agent:
        try:
            idx = next(i for i, a in enumerate(self.agents) if self._match_agent(identification, a))
            agent = self.agents.pop(idx)
        except StopIteration:
            agent = self._construct_agent(identification)
        agent = self._update_agent(agent, diff)
        self.agents.append(agent)
        return agent

    async def update_agent(self, identification: AgentIdentification, diff: AgentDiff) -> Agent:
        try:
            idx, agent = next(
                (i, a) for i, a in enumerate(self.agents) if self._match_agent(identification, a)
            )
        except StopIteration:
            raise AgentNotFound(identification)
        self.agents[idx] = agent = self._update_agent(agent, diff)
        return agent

    async def get_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        try:
            return next(w for w in self.workplaces if self._match_workplace(identification, w))
        except StopIteration:
            raise WorkplaceNotFound(identification)

    async def get_agent_workplaces(self, agent: Agent) -> List[Workplace]:
        return [w for w in self.workplaces if w.agent.id == agent.id]

    async def get_or_create_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        try:
            return next(w for w in self.workplaces if self._match_workplace(identification, w))
        except StopIteration:
            agent = await self.get_agent(identification.to_agent_identification())
            workplace = self._construct_workplace(identification, agent)
            self.workplaces.append(workplace)
            return workplace

    async def create_tag(self, name: str, created_by: Agent) -> Tag:
        if any(t.name == name for t in self.tags):
            raise TagAlreadyExists(name)
        tag = Tag(
            id=name, name=name, created_at_utc=datetime.now(timezone.utc), created_by=created_by
        )
        self.tags.append(tag)
        return tag

    async def find_all_tags(self) -> List[Tag]:
        return [*self.tags]

    async def get_or_create_conversation(self, customer: Customer) -> Conversation:
        try:
            conversation = next(
                c
                for c in self.conversations
                if c.customer.id == customer.id and c.state != ConversationState.RESOLVED
            )
        except StopIteration:
            conversation = Conversation(
                id=uuid4().hex,
                state=ConversationState.NEW,
                customer=customer,
                tags=[],
            )
            self.conversations.append(conversation)
        return conversation

    async def find_conversations_by_ids(
        self, conversation_ids: List[Any], with_messages: bool = False
    ) -> List[Conversation]:
        return [
            c if with_messages else self._strip_messages(c)
            for c in self.conversations
            if c.id in conversation_ids
        ]

    async def find_all_conversations(
        self, with_messages: bool = False
    ) -> AsyncIterator[Conversation]:
        for c in self.conversations:
            yield c if with_messages else self._strip_messages(c)

    async def count_all_conversations(self) -> int:
        return len(self.conversations)

    async def update_conversation(
        self, id: Any, diff: ConversationDiff, unassigned_only: bool = False
    ):
        try:
            idx = next(i for i, c in enumerate(self.conversations) if c.id == id)
        except StopIteration:
            raise ConversationNotFound()

        if unassigned_only and self.conversations[idx].assigned_agent is not None:
            raise ConversationAlreadyAssigned()

        conv = self.conversations.pop(idx)

        changes: Dict[str, Any] = {}
        if diff.state is not None:
            changes["state"] = diff.state
        if diff.assigned_workplace_id is SetNone:
            changes["assigned_workplace"] = None
            changes["assigned_agent"] = None
        elif diff.assigned_workplace_id is not None:
            workplace = await self.get_workplace(
                WorkplaceIdentification(id=diff.assigned_workplace_id)
            )
            changes["assigned_workplace"] = workplace
            changes["assigned_agent"] = workplace.agent
        if diff.customer_rating is not None:
            changes["customer_rating"] = diff.customer_rating
        if diff.added_tags or diff.removed_tags:
            added_tags = diff.added_tags or []
            removed_tag_names = {tag.name for tag in diff.removed_tags or []}
            filtered_tags = [tag for tag in conv.tags if tag.name not in removed_tag_names]
            changes["tags"] = [*filtered_tags, *added_tags]

        conv = replace(conv, **changes)
        self.conversations.append(conv)
        return conv

    async def get_agent_conversation(self, identification: WorkplaceIdentification) -> Conversation:
        try:
            return next(
                c
                for c in self.conversations
                if c.assigned_workplace
                and self._match_workplace(identification, c.assigned_workplace)
            )
        except StopIteration:
            raise ConversationNotFound()

    async def find_customer_conversations(
        self, customer: Customer, with_messages: bool = False
    ) -> List[Conversation]:
        return [
            c if with_messages else self._strip_messages(c)
            for c in self.conversations
            if c.customer.id == customer.id
        ]

    async def find_agent_conversations(
        self, agent: Agent, with_messages: bool = False
    ) -> List[Conversation]:
        return [
            c if with_messages else self._strip_messages(c)
            for c in self.conversations
            if c.assigned_agent and c.assigned_agent.id == agent.id
        ]

    async def save_message(self, conversation: Conversation, message: Message):
        try:
            idx = next(i for i, c in enumerate(self.conversations) if c.id == conversation.id)
            conv = self.conversations.pop(idx)
        except StopIteration:
            raise ConversationNotFound()
        conv = replace(conv, messages=[*conv.messages, message])
        self.conversations.append(conv)

    async def save_event(self, event: Event):
        self.events.append(event)

    async def find_all_events(self) -> AsyncIterator[Event]:
        for event in self.events:
            yield event

    async def count_all_events(self) -> int:
        return len(self.events)

    def _match_customer(self, identification: CustomerIdentification, customer: Customer) -> bool:
        return (
            (customer.id == identification.id is not None)
            or (customer.telegram_user_id == identification.telegram_user_id is not None)
            or (customer.shell_uuid == identification.shell_uuid is not None)
            or (
                customer.pubnub_user_id == identification.pubnub_user_id is not None
                and customer.pubnub_channel_id == identification.pubnub_channel_id is not None
            )
        )

    def _construct_customer(self, identification: CustomerIdentification) -> Customer:
        if identification.id is not None:
            raise ValueError("can't create customer with predefined ID")
        return Customer(
            id=uuid4().hex,
            telegram_user_id=identification.telegram_user_id,
            shell_uuid=identification.shell_uuid,
            pubnub_user_id=identification.pubnub_user_id,
            pubnub_channel_id=identification.pubnub_channel_id,
        )

    def _update_customer(self, customer: Customer, diff: Optional[CustomerDiff]) -> Customer:
        if diff is None:
            return customer
        changes: Dict[str, Any] = {
            "telegram_first_name": diff.telegram_first_name,
            "telegram_last_name": diff.telegram_last_name,
            "telegram_username": diff.telegram_username,
        }
        changes = {k: v for k, v in changes.items() if v is not None}
        return replace(customer, **changes)

    def _match_agent(self, identification: AgentIdentification, agent: Agent) -> bool:
        return (agent.id == identification.id is not None) or (
            agent.telegram_user_id == identification.telegram_user_id is not None
        )

    def _construct_agent(self, identification: AgentIdentification) -> Agent:
        if identification.id is not None:
            raise ValueError("can't create agent with predefined ID")
        return Agent(
            id=uuid4().hex,
            deactivated=False,
            telegram_user_id=identification.telegram_user_id,
        )

    def _update_agent(self, agent: Agent, diff: Optional[AgentDiff]) -> Agent:
        if diff is None:
            return agent
        changes: dict[str, Any] = {
            "deactivated": diff.deactivated,
            "telegram_first_name": diff.telegram_first_name,
            "telegram_last_name": diff.telegram_last_name,
            "telegram_username": diff.telegram_username,
        }
        changes = {k: v for k, v in changes.items() if v is not None}
        return replace(agent, **changes)

    def _match_workplace(
        self, identification: WorkplaceIdentification, workplace: Workplace
    ) -> bool:
        return (workplace.id == identification.id is not None) or (
            workplace.telegram_user_id == identification.telegram_user_id is not None
            and workplace.telegram_bot_id == identification.telegram_bot_id is not None
        )

    def _construct_workplace(
        self, identification: WorkplaceIdentification, agent: Agent
    ) -> Workplace:
        if identification.id is not None:
            raise ValueError("can't create workplace with predefined ID")
        return Workplace(
            id=uuid4().hex,
            telegram_user_id=identification.telegram_user_id,
            telegram_bot_id=identification.telegram_bot_id,
            agent=agent,
        )

    def _strip_messages(self, conv: Conversation) -> Conversation:
        return replace(conv, messages=UnavailableList[Message]())
