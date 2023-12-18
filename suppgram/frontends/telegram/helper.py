from typing import List, Optional

from telegram import Bot
from telegram.error import TelegramError

from suppgram.frontends.telegram import TelegramStorage
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.frontends.telegram.storage import TelegramChat, TelegramChatRole, TelegramMessage
from suppgram.helpers import flat_gather


class TelegramHelper:
    def __init__(
        self,
        manager_bot_token: Optional[str],
        app_manager: TelegramAppManager,
        storage: TelegramStorage,
    ):
        self._storage = storage
        self._manager_bot: Optional[Bot] = (
            app_manager.get_app(manager_bot_token).bot if manager_bot_token else None
        )

    async def check_belongs_to_agent_chats(self, telegram_user_id: int) -> List[TelegramChat]:
        chats = await self._storage.get_chats_by_role(TelegramChatRole.AGENTS)
        return [
            chat
            for chat in await flat_gather(
                self.check_belongs_to_group(telegram_user_id, group) for group in chats
            )
            if chat is not None
        ]

    async def check_belongs_to_group(
        self, telegram_user_id: int, group: TelegramChat
    ) -> Optional[TelegramChat]:
        if self._manager_bot is None:
            return None
        try:
            member = await self._manager_bot.get_chat_member(
                chat_id=group.telegram_chat_id, user_id=telegram_user_id
            )
            return (
                group
                if member.status in (member.ADMINISTRATOR, member.OWNER, member.MEMBER)
                else None
            )
        except TelegramError:  # TODO more precise exception handling
            return None

    async def delete_message_if_exists(self, message: TelegramMessage):
        if self._manager_bot is None:
            return
        try:
            await self._manager_bot.delete_message(
                chat_id=message.chat.telegram_chat_id,
                message_id=message.telegram_message_id,
            )
        except TelegramError:  # TODO more precise exception handling
            pass
