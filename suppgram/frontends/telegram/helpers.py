import functools
from itertools import zip_longest
from typing import Callable, TypeVar, Coroutine, List, Any

from telegram import Update, InlineKeyboardButton
from telegram.error import TelegramError
from telegram.ext import ContextTypes

T = TypeVar("T")


def send_text_answer(
    handler: Callable[[T, Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, str]]
) -> Callable[[T, Update, ContextTypes.DEFAULT_TYPE], Coroutine[None, None, None]]:
    @functools.wraps(handler)
    async def wrapped_handler(
        self: T, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        assert update.effective_chat
        answer = await handler(self, update, context)
        await context.bot.send_message(update.effective_chat.id, answer)

    return wrapped_handler


def arrange_buttons(
    buttons: List[InlineKeyboardButton],
) -> List[List[InlineKeyboardButton]]:
    it = iter(buttons)
    return [[b1] if b2 is None else [b1, b2] for b1, b2 in zip_longest(it, it)]


def is_chat_not_found(exc: TelegramError) -> bool:
    return "Chat not found" in str(exc)


def is_blocked_by_user(exc: TelegramError) -> bool:
    return "bot was blocked by the user" in str(exc)
