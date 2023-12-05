from typing import (
    List,
    Any,
    TypeVar,
    Optional,
    Mapping,
    Collection,
    MutableMapping,
)

from sqlalchemy import (
    select,
    update,
    Column,
)
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import (
    joinedload,
    selectinload,
)

from suppgram.entities import (
    CustomerIdentification,
    Customer as CustomerInterface,
    Agent as AgentInterface,
    WorkplaceIdentification,
    Workplace as WorkplaceInterface,
    Message as ConversaionMessageInterface,
    ConversationTag as ConversationTagInterface,
    Conversation as ConversationInterface,
    AgentIdentification,
    ConversationState,
    AgentDiff,
    ConversationDiff,
    SetNone,
    CustomerDiff,
)
from suppgram.errors import (
    ConversationNotFound,
    WorkplaceNotFound,
    AgentNotFound,
    ConversationAlreadyAssigned,
)
from suppgram.storage import Storage
from suppgram.storages.sqlalchemy.models import (
    Base,
    association_table,
    Conversation,
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
    ) -> CustomerInterface:
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
                await session.refresh(customer)
            elif diff is not None:
                self._models.apply_diff_to_customer_model(customer, diff)
                session.add(customer)
            return self._models.convert_from_customer_model(customer)

    async def get_agent(self, identification: AgentIdentification) -> AgentInterface:
        async with self._session() as session:
            query = select(self._models.agent_model).filter(
                self._models.make_agent_filter(identification)
            )
            agent = (await session.execute(query)).scalars().one_or_none()
            if agent is None:
                raise AgentNotFound(identification)
            return self._models.convert_from_agent_model(agent)

    async def create_or_update_agent(
        self, identification: AgentIdentification, diff: Optional[AgentDiff] = None
    ) -> AgentInterface:
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
                await session.refresh(agent)
            elif diff is not None:
                self._models.apply_diff_to_agent_model(agent, diff)
                session.add(agent)
            return self._models.convert_from_agent_model(agent)

    async def update_agent(
        self, identification: AgentIdentification, diff: AgentDiff
    ) -> AgentInterface:
        filter_ = self._models.make_agent_filter(identification)
        async with self._session() as session, session.begin():
            select_query = select(self._models.agent_model).filter(filter_).with_for_update()
            agent = (await session.execute(select_query)).scalars().one_or_none()
            if agent is None:
                raise AgentNotFound(identification)
            self._models.apply_diff_to_agent_model(agent, diff)
            session.add(agent)
            return self._models.convert_from_agent_model(agent)

    async def get_workplace(self, identification: WorkplaceIdentification) -> WorkplaceInterface:
        async with self._session() as session:
            query = select(self._models.workplace_model).filter(
                self._models.make_workplace_filter(identification)
            )
            workplace = (await session.execute(query)).scalars().one_or_none()
            if workplace is None:
                raise WorkplaceNotFound(identification)
            return workplace

    async def get_agent_workplaces(self, agent: AgentInterface) -> List[WorkplaceInterface]:
        async with self._session() as session:
            query = select(self._models.workplace_model).filter(
                self._models.make_agent_workplaces_filter(agent)
            )
            workplaces = (await session.execute(query)).scalars().all()
            return [
                self._models.convert_from_workplace_model(agent, workplace)
                for workplace in workplaces
            ]

    async def get_or_create_workplace(
        self, identification: WorkplaceIdentification
    ) -> WorkplaceInterface:
        agent_identification = identification.to_agent_identification()
        async with self._session() as session, session.begin():
            query = select(self._models.agent_model).where(
                self._models.make_agent_filter(agent_identification)
            )
            agent = (await session.execute(query)).scalars().one_or_none()
            if agent is None:
                raise AgentNotFound(agent_identification)
            query = (
                select(self._models.workplace_model, self._models.agent_model)
                .options(joinedload(self._models.workplace_model.agent))
                .filter(self._models.make_workplace_filter(identification))
            )
            workplace = (await session.execute(query)).scalars().one_or_none()
            if workplace is None:
                workplace = self._models.convert_to_workplace_model(agent.id, identification)
                session.add(workplace)
                await session.flush()
                await session.refresh(workplace)
            return self._models.convert_from_workplace_model(
                self._models.convert_from_agent_model(agent), workplace
            )

    async def create_tag(self, name: str, created_by: AgentInterface):
        async with self._session() as session, session.begin():
            tag = self._models.make_tag_model(name, created_by)
            session.add(tag)

    async def find_all_tags(self) -> List[ConversationTagInterface]:
        async with self._session() as session:
            query = select(self._models.conversation_tag_model).options(
                joinedload(self._models.conversation_tag_model.created_by)
            )
            tags = (await session.execute(query)).scalars().all()
            return [self._models.convert_from_tag_model(tag) for tag in tags]

    async def get_or_create_conversation(
        self, customer: CustomerInterface
    ) -> ConversationInterface:
        async with self._session() as session, session.begin():
            select_query = (
                select(self._models.conversation_model)
                .options(
                    joinedload(self._models.conversation_model.customer),
                    joinedload(self._models.conversation_model.assigned_workplace).joinedload(
                        self._models.workplace_model.agent
                    ),
                    selectinload(self._models.conversation_model.tags).joinedload(
                        self._models.conversation_tag_model.created_by
                    ),
                    selectinload(self._models.conversation_model.messages),
                )
                .filter(self._models.make_customer_conversation_filter(customer))
            )
            conv: Optional[Conversation] = (
                (await session.execute(select_query)).scalars().one_or_none()
            )
            assigned_agent: Optional[AgentInterface] = None
            assigned_workplace: Optional[WorkplaceInterface] = None
            if conv is None:
                conv = self._models.conversation_model(
                    customer_id=customer.id,
                    state=ConversationState.NEW,
                )
                session.add(conv)
                await session.flush()
                await session.refresh(conv)
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
                tags = [self._models.convert_from_tag_model(tag) for tag in conv.tags]
            return ConversationInterface(
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
    ) -> List[ConversationInterface]:
        async with self._session() as session:
            options = [
                joinedload(self._models.conversation_model.customer),
                joinedload(self._models.conversation_model.assigned_workplace).joinedload(
                    self._models.workplace_model.agent
                ),
                selectinload(self._models.conversation_model.tags).joinedload(
                    self._models.conversation_tag_model.created_by
                ),
            ]
            if with_messages:
                options.append(selectinload(self._models.conversation_model.messages))
            query = (
                select(self._models.conversation_model)
                .options(*options)
                .filter(self._models.make_conversations_filter(conversation_ids))
            )
            convs = (await session.execute(query)).scalars().all()
            return [
                self._models.convert_from_conversation_model(conv, with_messages=with_messages)
                for conv in convs
            ]

    async def update_conversation(
        self, id: Any, diff: ConversationDiff, unassigned_only: bool = False
    ):
        async with self._session() as session, session.begin():
            filter_ = self._models.make_conversations_filter([id])
            query = select(self._models.conversation_model).filter(filter_)
            conv = (await session.execute(query)).scalars().one_or_none()
            if conv is None:
                raise ConversationNotFound()

            if update_values := self._make_update_values(
                diff, exclude_fields=["added_tags", "removed_tags"]
            ):
                filter_ = self._models.make_conversations_filter(
                    [id], unassigned_only=unassigned_only
                )
                update_query = (
                    update(self._models.conversation_model).filter(filter_).values(**update_values)
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
                    Column("conversation_tag_id").in_(tag.id for tag in diff.removed_tags)
                )
                delete_query = association_table.delete().where(filter_)
                await session.execute(delete_query)

    async def get_agent_conversation(
        self, identification: WorkplaceIdentification
    ) -> ConversationInterface:
        try:
            async with self._session() as session, session.begin():
                options = [
                    joinedload(self._models.conversation_model.customer),
                    selectinload(self._models.conversation_model.tags).joinedload(
                        self._models.conversation_tag_model.created_by
                    ),
                    selectinload(self._models.conversation_model.messages),
                    joinedload(self._models.conversation_model.assigned_workplace).joinedload(
                        self._models.workplace_model.agent
                    ),
                ]
                query = (
                    select(
                        self._models.conversation_model,
                        self._models.workplace_model,
                        self._models.agent_model,
                    )
                    .filter(self._models.make_agent_conversation_filter(identification))
                    .options(*options)
                )
                conv = (await session.execute(query)).scalars().one()
                return self._models.convert_from_conversation_model(conv, with_messages=True)
        except NoResultFound as exc:
            raise ConversationNotFound() from exc

    async def save_message(
        self, conversation: ConversationInterface, message: ConversaionMessageInterface
    ):
        async with self._session() as session, session.begin():
            session.add(
                self._models.conversation_message_model(
                    conversation_id=conversation.id,
                    kind=message.kind,
                    time_utc=message.time_utc,
                    text=message.text,
                )
            )

    # TODO move to Models too, and maybe prefer updating model attributes with diffs?
    def _make_update_values(
        self, diff_dc: Any, exclude_fields: Collection[str] = ()
    ) -> Mapping[str, Any]:
        result: MutableMapping[str, Any] = {}
        for k, v in diff_dc.__dict__.items():
            if k in exclude_fields or v is None:
                continue
            if v is SetNone:
                v = None
            result[k] = v
        return result
