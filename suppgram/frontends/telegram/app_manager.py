from typing import List, Dict

from telegram.ext import Application, ApplicationBuilder


class TelegramAppManager:
    def __init__(self, tokens: List[str]):
        self._apps: Dict[str, Application] = {}
        for token in tokens:
            app = ApplicationBuilder().token(token).build()
            self._apps[token] = app

    def get_app(self, token: str) -> Application:
        return self._apps[token]
