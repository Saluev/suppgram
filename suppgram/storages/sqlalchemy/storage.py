from typing import (
    List,
    Any,
    TypeVar,
    Optional,
    AsyncIterator,
)

from sqlalchemy import (
    select,
    update,
    Column,
)
from sqlalchemy.exc import NoResultFound, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import (
    joinedload,
)
from sqlalchemy.sql.functions import count

from suppgram.entities import (
    Agent,
    AgentDiff,
    AgentIdentification,
    Conversation,
    ConversationDiff,
    ConversationState,
    Tag,
    Customer,
    CustomerDiff,
    CustomerIdentification,
    Message,
    Workplace,
    WorkplaceIdentification,
    Event,
)
from suppgram.errors import (
    ConversationNotFound,
    WorkplaceNotFound,
    AgentNotFound,
    ConversationAlreadyAssigned,
    TagAlreadyExists,
)
from suppgram.storage import Storage
from suppgram.storages.sqlalchemy.models import (
    Base,
    association_table,
    Models,
)

T = TypeVar("T", bound=Base)


class SQLAlchemyStorage(Storage):
    """Implementation of [Storage][suppgram.storage.Storage] for SQLAlchemy."""

    def __init__(self, engine: AsyncEngine, models: Models):
        """
        Parameters:
            engine: asynchronous SQLAlchemy engine
            models: collection of SQLAlchemy model types.
                    Allows using custom models, possibly enriched with some
                    business-specific fields or stripped of unnecessary columns
                    (e.g. for frontends you are not going to use)."""
        self._engine = engine
        self._models = models
        self._session = async_sessionmaker(bind=engine)

    async def initialize(self):
        await super().initialize()
        await self._models.initialize()

    async def create_or_update_customer(
        self,
        identification: CustomerIdentification,
        diff: Optional[CustomerDiff] = None,
    ) -> Customer:
        filter_ = self._models.make_customer_filter(identification)
        async with self._session() as session, session.begin():
            select_query = select(self._models.customer_model).where(filter_).with_for_update()
            customer = (await session.execute(select_query)).scalars().one_or_none()
            if customer is None:
                customer = self._models.convert_to_customer_model(identification)
                if diff is not None:
                    self._models.apply_diff_to_customer_model(customer, diff)
                session.add(customer)
                await session.flush()
            elif diff is not None:
                self._models.apply_diff_to_customer_model(customer, diff)
                session.add(customer)
            return self._models.convert_from_customer_model(customer)

    async def get_agent(self, identification: AgentIdentification) -> Agent:
        async with self._session() as session:
            select_query = select(self._models.agent_model).where(
                self._models.make_agent_filter(identification)
            )
            agent = (await session.execute(select_query)).scalars().one_or_none()
            if agent is None:
                raise AgentNotFound(identification)
            return self._models.convert_from_agent_model(agent)

    async def find_all_agents(self) -> AsyncIterator[Agent]:
        async with self._session() as session:
            select_query = select(self._models.agent_model)
            async for agent in await session.stream_scalars(select_query):
                yield self._models.convert_from_agent_model(agent)

    async def create_or_update_agent(
        self, identification: AgentIdentification, diff: Optional[AgentDiff] = None
    ) -> Agent:
        filter_ = self._models.make_agent_filter(identification)
        async with self._session() as session, session.begin():
            select_query = select(self._models.agent_model).where(filter_).with_for_update()
            agent = (await session.execute(select_query)).scalars().one_or_none()
            if agent is None:
                agent = self._models.convert_to_agent_model(identification)
                if diff is not None:
                    self._models.apply_diff_to_agent_model(agent, diff)
                session.add(agent)
                await session.flush()
            elif diff is not None:
                self._models.apply_diff_to_agent_model(agent, diff)
                session.add(agent)
            return self._models.convert_from_agent_model(agent)

    async def update_agent(self, identification: AgentIdentification, diff: AgentDiff) -> Agent:
        filter_ = self._models.make_agent_filter(identification)
        async with self._session() as session, session.begin():
            select_query = select(self._models.agent_model).where(filter_).with_for_update()
            agent = (await session.execute(select_query)).scalars().one_or_none()
            if agent is None:
                raise AgentNotFound(identification)
            self._models.apply_diff_to_agent_model(agent, diff)
            session.add(agent)
            return self._models.convert_from_agent_model(agent)

    async def get_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        async with self._session() as session:
            select_query = select(self._models.workplace_model).where(
                self._models.make_workplace_filter(identification)
            )
            workplace = (await session.execute(select_query)).scalars().one_or_none()
            if workplace is None:
                raise WorkplaceNotFound(identification)
            return workplace

    async def get_agent_workplaces(self, agent: Agent) -> List[Workplace]:
        async with self._session() as session:
            select_query = select(self._models.workplace_model).where(
                self._models.make_agent_workplaces_filter(agent)
            )
            workplaces = (await session.execute(select_query)).scalars().all()
            return [
                self._models.convert_from_workplace_model(agent, workplace)
                for workplace in workplaces
            ]

    async def get_or_create_workplace(self, identification: WorkplaceIdentification) -> Workplace:
        async with self._session() as session, session.begin():
            select_query = (
                select(self._models.workplace_model, self._models.agent_model)
                .options(joinedload(self._models.workplace_model.agent))
                .where(self._models.make_workplace_filter(identification))
            )
            workplace = (await session.execute(select_query)).scalars().one_or_none()
            if workplace is None:
                agent_identification = identification.to_agent_identification()
                select_query = select(self._models.agent_model).where(
                    self._models.make_agent_filter(agent_identification)
                )
                agent = (await session.execute(select_query)).scalars().one_or_none()
                if agent is None:
                    raise AgentNotFound(agent_identification)
                workplace = self._models.convert_to_workplace_model(agent.id, identification)
                session.add(workplace)
                await session.flush()
            else:
                agent = workplace.agent
            return self._models.convert_from_workplace_model(
                self._models.convert_from_agent_model(agent), workplace
            )

    async def create_tag(self, name: str, created_by: Agent) -> Tag:
        try:
            async with self._session() as session, session.begin():
                tag = self._models.make_tag_model(name, created_by)
                session.add(tag)
                await session.flush()
                return self._models.convert_from_tag_model(tag, created_by)
        except IntegrityError as exc:
            raise TagAlreadyExists(name) from exc

    async def find_all_tags(self) -> List[Tag]:
        async with self._session() as session:
            select_query = select(self._models.tag_model).options(
                joinedload(self._models.tag_model.created_by)
            )
            tags = (await session.execute(select_query)).scalars().all()
            return [
                self._models.convert_from_tag_model(
                    tag, self._models.convert_from_agent_model(tag.created_by)
                )
                for tag in tags
            ]

    async def get_or_create_conversation(self, customer: Customer) -> Conversation:
        async with self._session() as session, session.begin():
            options = self._models.make_conversation_options(with_messages=True)
            select_query = (
                select(self._models.conversation_model)
                .options(*options)
                .where(self._models.make_current_customer_conversation_filter(customer))
            )
            conv = (await session.execute(select_query)).scalars().one_or_none()
            assigned_agent: Optional[Agent] = None
            assigned_workplace: Optional[Workplace] = None
            if conv is None:
                conv = self._models.conversation_model(
                    customer_id=customer.id,
                    state=ConversationState.NEW,
                )
                session.add(conv)
                await session.flush()
                messages = []
                tags = []
            else:
                if conv.assigned_workplace:
                    assigned_agent = self._models.convert_from_agent_model(
                        conv.assigned_workplace.agent
                    )
                    assigned_workplace = self._models.convert_from_workplace_model(
                        assigned_agent, conv.assigned_workplace
                    )
                messages = [self._models.convert_from_message_model(msg) for msg in conv.messages]
                tags = [
                    self._models.convert_from_tag_model(
                        tag, self._models.convert_from_agent_model(tag.created_by)
                    )
                    for tag in conv.tags
                ]
            return Conversation(
                id=conv.id,
                state=conv.state,
                customer=customer,
                tags=tags,
                assigned_agent=assigned_agent,
                assigned_workplace=assigned_workplace,
                messages=messages,
            )

    async def find_conversations_by_ids(
        self, conversation_ids: List[Any], with_messages: bool = False
    ) -> List[Conversation]:
        async with self._session() as session:
            options = self._models.make_conversation_options(with_messages=with_messages)
            select_query = (
                select(self._models.conversation_model)
                .options(*options)
                .where(self._models.make_conversations_filter(conversation_ids))
            )
            convs = (await session.execute(select_query)).scalars().all()
            return [
                self._models.convert_from_conversation_model(conv, with_messages=with_messages)
                for conv in convs
            ]

    async def find_all_conversations(
        self, with_messages: bool = False
    ) -> AsyncIterator[Conversation]:
        async with self._session() as session:
            options = self._models.make_conversation_options(with_messages=with_messages)
            select_query = select(self._models.conversation_model).options(*options)
            async for conv in await session.stream_scalars(select_query):
                yield self._models.convert_from_conversation_model(
                    conv, with_messages=with_messages
                )

    async def count_all_conversations(self) -> int:
        async with self._session() as session:
            select_query = select(count(self._models.conversation_model.id))
            return (await session.execute(select_query)).scalar_one()

    async def update_conversation(
        self, id: Any, diff: ConversationDiff, unassigned_only: bool = False
    ):
        async with self._session() as session, session.begin():
            filter_ = self._models.make_conversations_filter([id])
            select_query = select(self._models.conversation_model).where(filter_)
            conv = (await session.execute(select_query)).scalars().one_or_none()
            if conv is None:
                raise ConversationNotFound()

            if update_values := self._models.make_conversation_update_values(diff):
                filter_ = self._models.make_conversations_filter(
                    [id], unassigned_only=unassigned_only
                )
                update_query = (
                    update(self._models.conversation_model).where(filter_).values(**update_values)
                )
                result = await session.execute(update_query)
                if unassigned_only and result.rowcount == 0:
                    raise ConversationAlreadyAssigned()

            if diff.added_tags:
                insert_query = association_table.insert().values(
                    [(conv.id, tag.id) for tag in diff.added_tags]
                )
                await session.execute(insert_query)

            if diff.removed_tags:
                filter_ = (Column("conversation_id") == conv.id) & (
                    Column("tag_id").in_(tag.id for tag in diff.removed_tags)
                )
                delete_query = association_table.delete().where(filter_)
                await session.execute(delete_query)

    async def get_agent_conversation(self, identification: WorkplaceIdentification) -> Conversation:
        try:
            async with self._session() as session:
                filter_ = self._models.make_workplace_conversation_filter(identification)
                options = self._models.make_conversation_options(with_messages=True)
                select_query = (
                    select(
                        self._models.conversation_model,
                        self._models.workplace_model,
                        self._models.agent_model,
                    )
                    .where(filter_)
                    .options(*options)
                )
                conv = (await session.execute(select_query)).scalars().one()
                return self._models.convert_from_conversation_model(conv, with_messages=True)
        except NoResultFound as exc:
            raise ConversationNotFound() from exc

    async def find_customer_conversations(
        self, customer: Customer, with_messages: bool = False
    ) -> List[Conversation]:
        async with self._session() as session:
            filter_ = self._models.make_customer_conversations_filter(customer.identification)
            options = self._models.make_conversation_options(with_messages=with_messages)
            select_query = (
                select(self._models.conversation_model, self._models.customer_model)
                .where(filter_)
                .options(*options)
            )
            convs = (await session.execute(select_query)).scalars().all()
            return [
                self._models.convert_from_conversation_model(conv, with_messages=with_messages)
                for conv in convs
            ]

    async def find_agent_conversations(
        self, agent: Agent, with_messages: bool = False
    ) -> List[Conversation]:
        async with self._session() as session:
            filter_ = self._models.make_agent_conversations_filter(agent.identification)
            options = self._models.make_conversation_options(with_messages=with_messages)
            select_query = (
                select(
                    self._models.conversation_model,
                    self._models.workplace_model,
                    self._models.agent_model,
                )
                .where(filter_)
                .options(*options)
            )
            convs = (await session.execute(select_query)).scalars().all()
            return [
                self._models.convert_from_conversation_model(conv, with_messages=with_messages)
                for conv in convs
            ]

    async def save_message(self, conversation: Conversation, message: Message):
        try:
            async with self._session() as session, session.begin():
                session.add(self._models.convert_to_message_model(conversation.id, message))
        except IntegrityError:
            raise ConversationNotFound()

    async def save_event(self, event: Event):
        async with self._session() as session, session.begin():
            session.add(self._models.convert_to_event_model(event))

    async def find_all_events(self) -> AsyncIterator[Event]:
        async with self._session() as session:
            select_query = select(self._models.event_model).order_by(self._models.event_model.id)
            async for event in await session.stream_scalars(select_query):
                yield self._models.convert_from_event_model(event)

    async def count_all_events(self) -> int:
        async with self._session() as session:
            select_query = select(count(self._models.event_model.id))
            return (await session.execute(select_query)).scalar_one()
