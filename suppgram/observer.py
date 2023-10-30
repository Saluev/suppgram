import asyncio
from typing import Callable, TypeVar, Generic, List, Awaitable

T = TypeVar("T")


class Observable(Generic[T]):
    def __init__(self):
        self._handlers: List[Callable[[T], Awaitable[None]]] = []

    def add_handler(
        self, handler: Callable[[T], Awaitable[None]]
    ) -> Callable[[T], Awaitable[None]]:
        self._handlers.append(handler)
        return handler  # can be used for decorator chaining

    async def trigger(self, event: T):
        await asyncio.gather(*(handler(event) for handler in self._handlers))
