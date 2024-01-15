import asyncio
import re
from typing import Iterable, Awaitable, Optional, AsyncIterator, Tuple, TypeVar


async def flat_gather(futures: Iterable[Awaitable]):
    """Like asyncio.gather(), but accepts iterable of
    coroutines rather than multiple arguments. Useful
    in list comprehensions."""
    return await asyncio.gather(*futures)


# The following function is taken from python-telegram-bot
# to avoid unnecessary dependencies.
def escape_markdown(text: str, entity_type: Optional[str] = None) -> str:
    """
    Helper function to escape telegram markup symbols.

    Args:
        text (:obj:`str`): The text.
        entity_type (:obj:`str`, optional): For the entity types ``PRE``, ``CODE`` and the link
            part of ``TEXT_LINKS``, only certain characters need to be escaped in ``MarkdownV2``.
            See the official API documentation for details. Only valid in combination with
            ``version=2``, will be ignored else.
    """
    if entity_type in ["pre", "code"]:
        escape_chars = r"\`"
    elif entity_type == "text_link":
        escape_chars = r"\)"
    else:
        escape_chars = r"_*[]()~`>#+-=|{}.!"

    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


T = TypeVar("T")


async def aenumerate(asequence: AsyncIterator[T], start=0) -> AsyncIterator[Tuple[int, T]]:
    """Asynchronously enumerate an async iterator from a given start value."""
    n = start
    async for elem in asequence:
        yield n, elem
        n += 1
