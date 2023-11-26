from logging import StreamHandler, LogRecord
from typing import Mapping


class ConfidentialStreamHandler(StreamHandler):
    def __init__(self, stream=None, replacements: Mapping[str, str] = {}):
        super().__init__(stream)
        self._replacements = replacements

    def format(self, record: LogRecord) -> str:
        result = super().format(record)
        for k, v in self._replacements.items():
            result = result.replace(k, v)
        return result
