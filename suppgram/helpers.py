import asyncio
from typing import Iterable, Awaitable


async def flat_gather(futures: Iterable[Awaitable]):
    """Like asyncio.gather(), but accepts iterable of
    coroutines rather than multiple arguments. Useful
    in list comprehensions."""
    return await asyncio.gather(*futures)
