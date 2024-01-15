from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict, Set, Awaitable, Callable

from suppgram.entities import Event, MessageKind, EventKind
from suppgram.helpers import aenumerate
from suppgram.storage import Storage


@dataclass(frozen=True)
class AgentAnalytics:
    agent_id: Any
    telegram_user_id: Optional[int]

    total_assigned: int
    total_resolved: int
    average_customer_rating: float
    average_assignment_to_resolution_time_min: float


@dataclass(frozen=True)
class ConversationAnalytics:
    conversation_id: Any
    customer_id: Any
    last_assigned_agent_id: Optional[Any]
    customer_rating: Optional[int]

    creation_time_utc: datetime
    first_assignment_time_utc: Optional[datetime]
    resolve_time_utc: Optional[datetime]

    last_message_kind: MessageKind
    last_message_time_utc: datetime


@dataclass(frozen=True)
class Report:
    agents: List[AgentAnalytics]
    conversations: List[ConversationAnalytics]
    events: List[Event]

    average_start_to_first_response_time_min: float
    average_start_to_resolution_time_min: float
    average_customer_rating: float


ProgressCallback = Callable[[float], Awaitable[None]]


@dataclass
class _ConversationState:
    conversation_id: Any
    last_assigned_agent_id: Optional[Any] = None

    creation_time_utc: Optional[datetime] = None
    first_assignment_time_utc: Optional[datetime] = None
    first_response_time_utc: Optional[datetime] = None
    last_assignment_time_utc: Optional[datetime] = None
    resolve_time_utc: Optional[datetime] = None

    last_message_kind: Optional[MessageKind] = None
    last_message_time_utc: Optional[datetime] = None


class Reporter:
    def __init__(self, storage: Storage):
        self._storage = storage

    async def report(self, progress_callback: Optional[ProgressCallback]) -> Report:
        if progress_callback is not None:
            await progress_callback(0.0)
        total_events = await self._storage.count_all_events()
        total_conversations = await self._storage.count_all_conversations()
        total_steps = max(1, total_events + total_conversations)
        # Might also count agents, but there are probably going
        # to be very few compared to conversations and events.

        conversation_states: Dict[Any, _ConversationState] = {}
        agent_assignments: Dict[Any, Set[Any]] = defaultdict(set)
        agent_resolutions: Dict[Any, Set[Any]] = defaultdict(set)
        agent_ratings: Dict[Any, List[int]] = defaultdict(list)
        agent_resolution_times: Dict[Any, List[timedelta]] = defaultdict(list)

        def _conv_state(conv_id: Any) -> _ConversationState:
            conversation_states.setdefault(conv_id, _ConversationState(conversation_id=conv_id))
            return conversation_states[conv_id]

        events: List[Event] = []
        async for i, event in aenumerate(self._storage.find_all_events()):
            events.append(event)
            conv_state = _conv_state(event.conversation_id)

            if event.kind == EventKind.AGENT_ASSIGNED:
                conv_state.last_assigned_agent_id = event.agent_id
                if not conv_state.first_assignment_time_utc:
                    conv_state.first_assignment_time_utc = event.time_utc
                conv_state.last_assignment_time_utc = event.time_utc
                agent_assignments[event.agent_id].add(event.conversation_id)

            elif event.kind == EventKind.CONVERSATION_POSTPONED:
                pass

            elif event.kind == EventKind.CONVERSATION_RATED:
                # We'll only take into account final ratings stored in conversations.
                # Rating will be attributed to the last agent assigned to a conversation.
                pass

            elif event.kind == EventKind.CONVERSATION_RESOLVED:
                conv_state.resolve_time_utc = event.time_utc
                agent_resolutions[conv_state.last_assigned_agent_id].add(event.conversation_id)
                if conv_state.last_assignment_time_utc:
                    agent_resolution_times[conv_state.last_assigned_agent_id].append(
                        event.time_utc - conv_state.last_assignment_time_utc
                    )

            elif event.kind == EventKind.CONVERSATION_STARTED:
                conv_state.creation_time_utc = event.time_utc

            elif event.kind == EventKind.CONVERSATION_TAG_ADDED:
                pass

            elif event.kind == EventKind.CONVERSATION_TAG_REMOVED:
                pass

            elif event.kind == EventKind.MESSAGE_SENT:
                if (
                    event.message_kind == MessageKind.FROM_AGENT
                    and not conv_state.first_response_time_utc
                ):
                    conv_state.first_response_time_utc = event.time_utc
                if event.message_kind in (MessageKind.FROM_AGENT, MessageKind.FROM_CUSTOMER):
                    conv_state.last_message_kind = event.message_kind
                    conv_state.last_message_time_utc = event.time_utc

            if progress_callback is not None:
                await progress_callback((i + 1) / total_steps)

        conversations: List[ConversationAnalytics] = []
        async for i, conv in aenumerate(self._storage.find_all_conversations()):
            conv_state = _conv_state(conv.id)
            if (
                not conv_state.creation_time_utc
                or not conv_state.last_message_kind
                or not conv_state.last_message_time_utc
            ):
                # Not a single message within conversation — ignoring it.
                continue

            if conv.customer_rating is not None and conv_state.last_assigned_agent_id is not None:
                agent_ratings[conv_state.last_assigned_agent_id].append(conv.customer_rating)
            conversations.append(
                ConversationAnalytics(
                    conversation_id=conv.id,
                    customer_id=conv.customer.id,
                    last_assigned_agent_id=conv_state.last_assigned_agent_id,
                    customer_rating=conv.customer_rating,
                    creation_time_utc=conv_state.creation_time_utc,
                    first_assignment_time_utc=conv_state.first_assignment_time_utc,
                    resolve_time_utc=conv_state.resolve_time_utc,
                    last_message_kind=conv_state.last_message_kind,
                    last_message_time_utc=conv_state.last_message_time_utc,
                )
            )

            if progress_callback is not None:
                await progress_callback((total_events + i + 1) / total_steps)

        agents = [
            AgentAnalytics(
                agent_id=agent.id,
                telegram_user_id=agent.telegram_user_id,
                total_assigned=len(agent_assignments[agent.id]),
                total_resolved=len(agent_resolutions[agent.id]),
                average_customer_rating=sum(agent_ratings[agent.id]) / len(agent_ratings[agent.id])
                if agent_ratings[agent.id]
                else float("nan"),
                average_assignment_to_resolution_time_min=sum(
                    td.total_seconds() / 60.0 for td in agent_resolution_times[agent.id]
                )
                / len(agent_resolution_times[agent.id])
                if agent_resolution_times[agent.id]
                else float("nan"),
            )
            async for agent in self._storage.find_all_agents()
        ]

        first_response_times_min = [
            (conv_state.first_response_time_utc - conv_state.creation_time_utc).total_seconds()
            / 60.0
            for conv_state in conversation_states.values()
            if conv_state.creation_time_utc and conv_state.first_response_time_utc
        ]
        resolution_times_min = [
            (conv_state.resolve_time_utc - conv_state.creation_time_utc).total_seconds() / 60.0
            for conv_state in conversation_states.values()
            if conv_state.creation_time_utc and conv_state.resolve_time_utc
        ]
        ratings = [
            conv.customer_rating for conv in conversations if conv.customer_rating is not None
        ]

        return Report(
            agents=agents,
            conversations=conversations,
            events=events,
            average_start_to_first_response_time_min=sum(first_response_times_min)
            / len(first_response_times_min)
            if first_response_times_min
            else float("nan"),
            average_start_to_resolution_time_min=sum(resolution_times_min)
            / len(resolution_times_min)
            if resolution_times_min
            else float("nan"),
            average_customer_rating=sum(ratings) / len(ratings) if ratings else float("nan"),
        )
