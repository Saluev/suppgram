from typing import List, Mapping, cast

from suppgram.backend import WorkplaceManager
from suppgram.entities import Agent, Workplace, WorkplaceIdentification
from suppgram.frontends.telegram.app_manager import TelegramAppManager
from suppgram.helpers import flat_gather


class TelegramWorkplaceManager(WorkplaceManager):
    def __init__(self, tokens: List[str], app_manager: TelegramAppManager):
        self._tokens = tokens
        self._app_manager = app_manager
        self._bot_id_to_index: Mapping[int, int] = {}

    async def initialize(self):
        await super().initialize()
        await flat_gather(self._app_manager.get_app(token).initialize() for token in self._tokens)

    def create_missing_workplaces(
        self, agent: Agent, existing_workplaces: List[Workplace]
    ) -> List[WorkplaceIdentification]:
        bot_ids = self._get_bot_id_to_index()
        present_bot_ids = {workplace.telegram_bot_id for workplace in existing_workplaces}
        missing_bot_ids = set(bot_ids.keys()) - present_bot_ids
        return [
            WorkplaceIdentification(telegram_user_id=agent.telegram_user_id, telegram_bot_id=bot_id)
            for bot_id in missing_bot_ids
        ]

    def filter_and_rank_available_workplaces(self, workplaces: List[Workplace]) -> List[Workplace]:
        bot_ids = self._get_bot_id_to_index()
        available_workplaces = [
            workplace for workplace in workplaces if workplace.telegram_bot_id in bot_ids
        ]
        available_workplaces.sort(key=lambda w: bot_ids[cast(int, w.telegram_bot_id)])
        return available_workplaces

    def _get_bot_id_to_index(self) -> Mapping[int, int]:
        if not self._bot_id_to_index:
            self._bot_id_to_index = {
                self._app_manager.get_app(token).bot.id: idx
                for idx, token in enumerate(self._tokens)
            }
        return self._bot_id_to_index
