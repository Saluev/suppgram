import functools
from itertools import zip_longest
from typing import Callable, TypeVar, Iterable, Coroutine, List

from telegram import Update, InlineKeyboardButton
from telegram.ext import ContextTypes

T = TypeVar("T")


def send_text_answer(
    handler: Callable[
        [T, Update, ContextTypes.DEFAULT_TYPE], Coroutine[None, None, str]
    ]
) -> Callable[[T, Update, ContextTypes.DEFAULT_TYPE], Coroutine[None, None, None]]:
    @functools.wraps(handler)
    async def wrapped_handler(
        self: T, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        answer = await handler(self, update, context)
        await context.bot.send_message(update.effective_chat.id, answer)

    return wrapped_handler


def send_text_answers(
    handler: Callable[
        [T, Update, ContextTypes.DEFAULT_TYPE], Coroutine[None, None, Iterable[str]]
    ]
) -> Callable[[T, Update, ContextTypes.DEFAULT_TYPE], Coroutine[None, None, None]]:
    @functools.wraps(handler)
    async def wrapped_handler(
        self: T, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        for answer in await handler(self, update, context):
            await context.bot.send_message(update.effective_chat.id, answer)

    return wrapped_handler


def arrange_buttons(
    buttons: List[InlineKeyboardButton],
) -> List[List[InlineKeyboardButton]]:
    it = iter(buttons)
    return [[b1] if b2 is None else [b1, b2] for b1, b2 in zip_longest(it, it)]
