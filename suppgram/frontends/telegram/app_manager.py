from typing import List, Mapping

from telegram.ext import Application, ApplicationBuilder


class TelegramAppManager:
    def __init__(self, apps: List[Application]):
        self._apps: Mapping[str, Application] = {app.bot.token: app for app in apps}

    @classmethod
    def from_tokens(cls, tokens: List[str]):
        apps = [ApplicationBuilder().token(token).build() for token in tokens]
        return cls(apps)

    def get_app(self, token: str) -> Application:
        return self._apps[token]
