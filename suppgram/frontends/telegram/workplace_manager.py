from typing import List, Optional, Set

from suppgram.entities import Agent, Workplace, WorkplaceIdentification
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.helpers import flat_gather
from suppgram.interfaces import WorkplaceManager


class TelegramWorkplaceManager(WorkplaceManager):
    def __init__(self, tokens: List[str], app_manager: TelegramAppManager):
        self._tokens = tokens
        self._app_manager = app_manager
        self._bot_ids: Optional[Set[int]] = None

    async def initialize(self):
        await super().initialize()
        await flat_gather(
            self._app_manager.get_app(token).initialize() for token in self._tokens
        )

    def create_missing_workplaces(
        self, agent: Agent, existing_workplaces: List[Workplace]
    ) -> List[WorkplaceIdentification]:
        bot_ids = self._get_bot_ids()
        present_bot_ids = {
            workplace.telegram_bot_id for workplace in existing_workplaces
        }
        missing_bot_ids = bot_ids - present_bot_ids
        return [
            WorkplaceIdentification(
                telegram_user_id=agent.telegram_user_id, telegram_bot_id=bot_id
            )
            for bot_id in missing_bot_ids
        ]

    def filter_available_workplaces(
        self, workplaces: List[Workplace]
    ) -> List[Workplace]:
        return [
            workplace
            for workplace in workplaces
            if workplace.telegram_bot_id in self._bot_ids
        ]

    def _get_bot_ids(self) -> Set[int]:
        if self._bot_ids is None:
            self._bot_ids = {
                self._app_manager.get_app(token).bot.id for token in self._tokens
            }
        return self._bot_ids
