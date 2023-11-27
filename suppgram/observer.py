import abc
import asyncio
from typing import Callable, TypeVar, Generic, List, Awaitable

from suppgram.helpers import flat_gather

T = TypeVar("T")


class Observable(Generic[T], abc.ABC):
    @abc.abstractmethod
    def add_handler(
        self, handler: Callable[[T], Awaitable[None]]
    ) -> Callable[[T], Awaitable[None]]:
        pass

    @abc.abstractmethod
    def add_batch_handler(
        self, handler: Callable[[List[T]], Awaitable[None]]
    ) -> Callable[[List[T]], Awaitable[None]]:
        pass

    @abc.abstractmethod
    async def trigger(self, event: T):
        pass

    @abc.abstractmethod
    async def trigger_batch(self, events: List[T]):
        pass


class LocalObservable(Observable[T]):
    def __init__(self) -> None:
        self._handlers: List[Callable[[T], Awaitable[None]]] = []
        self._batch_handlers: List[Callable[[List[T]], Awaitable[None]]] = []

    def add_handler(
        self, handler: Callable[[T], Awaitable[None]]
    ) -> Callable[[T], Awaitable[None]]:
        self._handlers.append(handler)
        return handler  # return value can be used for decorator chaining

    def add_batch_handler(
        self, handler: Callable[[List[T]], Awaitable[None]]
    ) -> Callable[[List[T]], Awaitable[None]]:
        self._batch_handlers.append(handler)
        return handler  # return value can be used for decorator chaining

    async def trigger(self, event: T):
        await asyncio.gather(
            flat_gather(handler(event) for handler in self._handlers),
            flat_gather(handler([event]) for handler in self._batch_handlers),
        )

    async def trigger_batch(self, events: List[T]):
        await asyncio.gather(
            flat_gather(
                handler(event) for handler in self._handlers for event in events
            ),
            flat_gather(handler(events) for handler in self._batch_handlers),
        )
