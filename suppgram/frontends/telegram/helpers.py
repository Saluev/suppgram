import functools
import json
from itertools import zip_longest
from typing import Callable, TypeVar, Coroutine, List, Any, Iterable, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from suppgram.frontends.telegram.callback_actions import CallbackActionKind
from suppgram.frontends.telegram.storage import TelegramMessage

T = TypeVar("T")


def send_text_answer(
    handler: Callable[[T, Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, str]]
) -> Callable[[T, Update, ContextTypes.DEFAULT_TYPE], Coroutine[None, None, None]]:
    @functools.wraps(handler)
    async def wrapped_handler(self: T, update: Update, context: ContextTypes.DEFAULT_TYPE):
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


def encode_callback_data(doc: Any) -> str:
    return json.dumps(doc, separators=(",", ":"))


def decode_callback_data(data: str) -> Any:
    return json.loads(data)


def paginate_texts(
    prefix: str,
    texts: Iterable[str],
    suffix: str,
    delimiter: str = "\n",
    max_page_lines: int = 4000,
    max_page_chars: int = 4000,
) -> Iterable[str]:
    prefix_newlines = prefix.count("\n")
    delimiter_newlines = delimiter.count("\n")
    parts, parts_length, parts_newlines = [prefix], len(prefix), prefix_newlines
    suffix_newlines = suffix.count("\n")
    for text in texts:
        text_newlines = text.count("\n")
        page_length = parts_length + len(delimiter) + len(text) + len(delimiter) + len(suffix)
        page_newlines = (
            parts_newlines
            + delimiter_newlines
            + text_newlines
            + delimiter_newlines
            + suffix_newlines
        )
        if page_length > max_page_chars or page_newlines >= max_page_lines:
            parts.append(suffix)
            yield "".join(parts)
            parts, parts_length, parts_newlines = [prefix], len(prefix), prefix_newlines
        if parts_length > 0:
            parts.append(delimiter)
            parts_length += len(delimiter)
            parts_newlines += delimiter_newlines
        parts.append(text)
        parts_length += len(text)
        parts_newlines += text_newlines
    if parts_length > 0:
        parts.append(suffix)
        yield "".join(parts)


def make_pagination_keyboard(
    message: TelegramMessage, number_of_pages: int, current_page_idx: int
) -> Optional[InlineKeyboardMarkup]:
    if number_of_pages <= 1:
        return None

    if number_of_pages <= 5:
        min_page_idx, max_page_idx = 0, number_of_pages
    elif current_page_idx < 2:
        min_page_idx, max_page_idx = 0, 5
    elif current_page_idx + 3 >= number_of_pages:
        min_page_idx, max_page_idx = number_of_pages - 5, number_of_pages
    else:
        min_page_idx, max_page_idx = current_page_idx - 2, current_page_idx + 3

    buttons: List[InlineKeyboardButton] = []
    for page_idx in range(min_page_idx, max_page_idx):
        text = str(page_idx + 1)
        if page_idx == current_page_idx:
            buttons.append(InlineKeyboardButton(text=f"〈{text}〉", callback_data="{}"))
            continue
        if 0 < min_page_idx == page_idx:
            text = "«"
        if page_idx + 1 == max_page_idx < number_of_pages:
            text = "»"
        buttons.append(_make_pagination_button(message, text, page_idx))

    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def _make_pagination_button(
    message: TelegramMessage, text: str, page_idx: int
) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=encode_callback_data(
            {
                "a": CallbackActionKind.PAGE,
                "c": message.chat.telegram_chat_id,
                "m": message.telegram_message_id,
                "p": page_idx,
            },
        ),
    )
