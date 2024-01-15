import abc
from typing import List, Any, Optional, AsyncIterator

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
    CustomerDiff,
    Tag,
    Event,
)


class Storage(abc.ABC):
    """
    Storage encapsulates functionality related to storing data persistently in a database,
    allowing to integrate Suppgram into systems with various tech stacks.

    Basically implements Repository design pattern.
    """

    async def initialize(self):
        """Performs asynchronous initialization if needed."""

    @abc.abstractmethod
    async def create_or_update_customer(
        self,
        identification: CustomerIdentification,
        diff: Optional[CustomerDiff] = None,
    ) -> Customer:
        """Creates or updates customer identified by given `identification` with new data provided in `diff`.

        Can be used with `diff=None` to get already existing customer with no changes applied.

        Parameters:
            identification: data necessary to uniquely identify the customer.
            diff: optional metadata to be updated.
        """

    @abc.abstractmethod
    async def get_agent(self, identification: AgentIdentification) -> Agent:
        pass

    @abc.abstractmethod
    def find_all_agents(self) -> AsyncIterator[Agent]:
        pass

    @abc.abstractmethod
    async def create_or_update_agent(
        self, identification: AgentIdentification, diff: Optional[AgentDiff] = None
    ) -> Agent:
        pass

    @abc.abstractmethod
    async def update_agent(self, identification: AgentIdentification, diff: AgentDiff) -> Agent:
        pass

    @abc.abstractmethod
    async def get_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        pass

    @abc.abstractmethod
    async def get_agent_workplaces(self, agent: Agent) -> List[Workplace]:
        pass

    @abc.abstractmethod
    async def get_or_create_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        pass

    @abc.abstractmethod
    async def create_tag(self, name: str, created_by: Agent) -> Tag:
        pass

    @abc.abstractmethod
    async def find_all_tags(self) -> List[Tag]:
        pass

    @abc.abstractmethod
    async def get_or_create_conversation(self, customer: Customer) -> Conversation:
        pass

    @abc.abstractmethod
    async def find_conversations_by_ids(
        self, conversation_ids: List[Any], with_messages: bool = False
    ) -> List[Conversation]:
        pass

    @abc.abstractmethod
    def find_all_conversations(self, with_messages: bool = False) -> AsyncIterator[Conversation]:
        pass

    @abc.abstractmethod
    async def count_all_conversations(self) -> int:
        pass

    @abc.abstractmethod
    async def update_conversation(
        self, id: Any, diff: ConversationDiff, unassigned_only: bool = False
    ):
        pass

    @abc.abstractmethod
    async def get_agent_conversation(self, identification: WorkplaceIdentification) -> Conversation:
        pass

    @abc.abstractmethod
    async def find_customer_conversations(
        self, customer: Customer, with_messages: bool = False
    ) -> List[Conversation]:
        pass

    @abc.abstractmethod
    async def find_agent_conversations(
        self, agent: Agent, with_messages: bool = False
    ) -> List[Conversation]:
        pass

    @abc.abstractmethod
    async def save_message(self, conversation: Conversation, message: Message):
        pass

    @abc.abstractmethod
    async def save_event(self, event: Event):
        pass

    @abc.abstractmethod
    def find_all_events(self) -> AsyncIterator[Event]:
        """Iterate over all stored events in chronological order."""

    @abc.abstractmethod
    async def count_all_events(self) -> int:
        pass
