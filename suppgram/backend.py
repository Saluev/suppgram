import abc
from typing import Any, List, Optional

from suppgram.entities import (
    ConversationEvent,
    NewMessageForCustomerEvent,
    NewUnassignedMessageFromCustomerEvent,
    NewMessageForAgentEvent,
    AgentIdentification,
    Agent,
    AgentDiff,
    CustomerIdentification,
    Conversation,
    WorkplaceIdentification,
    Workplace,
    Message,
    CustomerDiff,
    Tag,
    ConversationTagEvent,
    Customer,
    TagEvent,
)
from suppgram.observer import Observable


class Backend(abc.ABC):
    on_new_conversation: Observable[ConversationEvent]
    on_conversation_assignment: Observable[ConversationEvent]
    on_conversation_resolution: Observable[ConversationEvent]
    on_conversation_tag_added: Observable[ConversationTagEvent]
    on_conversation_tag_removed: Observable[ConversationTagEvent]
    on_conversation_rated: Observable[ConversationEvent]
    on_new_message_for_customer: Observable[NewMessageForCustomerEvent]
    on_new_unassigned_message_from_customer: Observable[NewUnassignedMessageFromCustomerEvent]
    on_new_message_for_agent: Observable[NewMessageForAgentEvent]
    on_tag_created: Observable[TagEvent]

    @abc.abstractmethod
    async def create_or_update_agent(
        self, identification: AgentIdentification, diff: Optional[AgentDiff] = None
    ) -> Agent:
        pass

    @abc.abstractmethod
    async def identify_agent(self, identification: AgentIdentification) -> Agent:
        pass

    @abc.abstractmethod
    async def update_agent(self, identification: AgentIdentification, diff: AgentDiff) -> Agent:
        pass

    @abc.abstractmethod
    async def deactivate_agent(self, agent: Agent):
        pass

    @abc.abstractmethod
    async def create_or_update_customer(
        self, identification: CustomerIdentification, diff: Optional[CustomerDiff] = None
    ) -> Customer:
        pass

    @abc.abstractmethod
    async def identify_customer_conversation(
        self, identification: CustomerIdentification
    ) -> Conversation:
        pass

    @abc.abstractmethod
    async def identify_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        pass

    @abc.abstractmethod
    async def create_tag(self, name: str, created_by: Agent) -> Tag:
        pass

    @abc.abstractmethod
    async def get_all_tags(self) -> List[Tag]:
        pass

    @abc.abstractmethod
    async def identify_agent_conversation(
        self, identification: WorkplaceIdentification
    ) -> Conversation:
        pass

    @abc.abstractmethod
    async def process_message(self, conversation: Conversation, message: Message):
        pass

    @abc.abstractmethod
    async def assign_agent(self, assigner: Agent, assignee: Agent, conversation_id: Any):
        pass

    async def get_conversation(self, conversation_id: Any) -> Conversation:
        return (await self.get_conversations([conversation_id], with_messages=True))[0]

    @abc.abstractmethod
    async def get_conversations(
        self, conversation_ids: List[Any], with_messages: bool = False
    ) -> List[Conversation]:
        pass

    @abc.abstractmethod
    async def get_customer_conversations(self, customer: Customer) -> List[Conversation]:
        pass

    @abc.abstractmethod
    async def add_tag_to_conversation(self, conversation: Conversation, tag: Tag):
        pass

    @abc.abstractmethod
    async def remove_tag_from_conversation(self, conversation: Conversation, tag: Tag):
        pass

    @abc.abstractmethod
    async def rate_conversation(self, conversation: Conversation, rating: int):
        pass

    @abc.abstractmethod
    async def postpone_conversation(self, resolver: Agent, conversation: Conversation):
        pass

    @abc.abstractmethod
    async def resolve_conversation(self, resolver: Agent, conversation: Conversation):
        pass


class WorkplaceManager(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    def create_missing_workplaces(
        self, agent: Agent, existing_workplaces: List[Workplace]
    ) -> List[WorkplaceIdentification]:
        pass

    def filter_and_rank_available_workplaces(self, workplaces: List[Workplace]) -> List[Workplace]:
        return workplaces
