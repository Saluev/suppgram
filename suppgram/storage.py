import abc
from typing import List, Any

from suppgram.entities import (
    CustomerIdentification,
    Customer,
    AgentIdentification,
    Agent,
    AgentDiff,
    WorkplaceIdentification,
    Workplace,
    Conversation,
    Message,
    ConversationDiff,
)


class Storage(abc.ABC):
    async def initialize(self):
        pass

    @abc.abstractmethod
    async def get_or_create_customer(
        self, identification: CustomerIdentification
    ) -> Customer:
        pass

    @abc.abstractmethod
    async def get_agent(self, identification: AgentIdentification) -> Agent:
        pass

    @abc.abstractmethod
    async def create_agent(self, identification: AgentIdentification) -> Agent:
        pass

    @abc.abstractmethod
    async def update_agent(self, identification: AgentIdentification, diff: AgentDiff):
        pass

    @abc.abstractmethod
    async def get_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        pass

    @abc.abstractmethod
    async def get_agent_workplaces(self, agent: Agent) -> List[Workplace]:
        pass

    @abc.abstractmethod
    async def get_or_create_workplace(
        self, agent: Agent, identification: WorkplaceIdentification
    ) -> Workplace:
        pass

    @abc.abstractmethod
    async def get_or_create_conversation(self, customer: Customer) -> Conversation:
        pass

    @abc.abstractmethod
    async def get_conversations(
        self, conversation_ids: List[Any], with_messages: bool = False
    ) -> List[Conversation]:
        pass

    @abc.abstractmethod
    async def update_conversation(
        self, id: Any, diff: ConversationDiff, unassigned_only: bool = False
    ):
        pass

    @abc.abstractmethod
    async def get_agent_conversation(
        self, identification: WorkplaceIdentification
    ) -> Conversation:
        pass

    @abc.abstractmethod
    async def save_message(self, conversation: Conversation, message: Message):
        pass
