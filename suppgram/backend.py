import abc
from typing import Any, List

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
    ConversationTag,
    ConversationTagEvent,
)
from suppgram.observer import Observable
from suppgram.permissions import Permission


class Backend(abc.ABC):
    on_new_conversation: Observable[ConversationEvent]
    on_conversation_assignment: Observable[ConversationEvent]
    on_conversation_resolution: Observable[ConversationEvent]
    on_conversation_tag_added: Observable[ConversationTagEvent]
    on_conversation_tag_removed: Observable[ConversationTagEvent]
    on_conversation_rated: Observable[ConversationEvent]
    on_new_message_for_customer: Observable[NewMessageForCustomerEvent]
    on_new_unassigned_message_from_customer: Observable[
        NewUnassignedMessageFromCustomerEvent
    ]
    on_new_message_for_agent: Observable[NewMessageForAgentEvent]

    @abc.abstractmethod
    async def create_agent(self, identification: AgentIdentification) -> Agent:
        pass

    @abc.abstractmethod
    async def identify_agent(self, identification: AgentIdentification) -> Agent:
        pass

    @abc.abstractmethod
    async def update_agent(self, identification: AgentIdentification, diff: AgentDiff):
        pass

    @abc.abstractmethod
    async def create_or_update_customer(
        self, identification: CustomerIdentification, diff: CustomerDiff
    ):
        pass

    @abc.abstractmethod
    async def identify_customer_conversation(
        self, identification: CustomerIdentification
    ) -> Conversation:
        pass

    @abc.abstractmethod
    async def identify_workplace(
        self, identification: WorkplaceIdentification
    ) -> Workplace:
        pass

    @abc.abstractmethod
    def check_permission(self, agent: Agent, permission: Permission) -> bool:
        pass

    @abc.abstractmethod
    async def create_tag(self, name: str, created_by: Agent):
        pass

    @abc.abstractmethod
    async def get_all_tags(self) -> List[ConversationTag]:
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
    async def assign_agent(
        self, assigner: Agent, assignee: Agent, conversation_id: Any
    ):
        pass

    async def get_conversation(self, conversation_id: Any) -> Conversation:
        return (await self.get_conversations([conversation_id], with_messages=True))[0]

    @abc.abstractmethod
    async def get_conversations(
        self, conversation_ids: List[Any], with_messages: bool = False
    ) -> List[Conversation]:
        pass

    @abc.abstractmethod
    async def add_tag_to_conversation(
        self, conversation: Conversation, tag: ConversationTag
    ):
        pass

    @abc.abstractmethod
    async def remove_tag_from_conversation(
        self, conversation: Conversation, tag: ConversationTag
    ):
        pass

    @abc.abstractmethod
    async def rate_conversation(self, conversation: Conversation, rating: int):
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

    def filter_available_workplaces(
        self, workplaces: List[Workplace]
    ) -> List[Workplace]:
        return workplaces
