from __future__ import annotations

import time
import traceback

TELEGRAM_TEXT_LIMIT = 4096
REPORT_LIMIT = 3500

USER_ERROR_TEXT = (
    "Что-то пошло не так, действие не выполнено. "
    "Попробуйте еще раз или откройте меню командой /start."
)


def build_admin_report(exc: BaseException, context: str) -> str:
    """Plain-text report for owners; always shorter than one Telegram message."""
    # The message is already in the header; keep the frames, newest last.
    tail = "".join(traceback.format_tb(exc.__traceback__))
    header = f"Ошибка в боте\nГде: {context}\nЧто: {type(exc).__name__}: {exc}"[:1000]
    room = REPORT_LIMIT - len(header) - 2
    if len(tail) > room:
        tail = "…" + tail[-(room - 1):]
    report = f"{header}\n\n{tail}"
    return report[:TELEGRAM_TEXT_LIMIT]


class ReportThrottle:
    """Lets the same kind of error reach owners at most once per window."""

    def __init__(self, window_seconds: float = 600, clock=time.monotonic):
        self.window_seconds = window_seconds
        self.clock = clock
        self._last_sent: dict[str, float] = {}

    def should_send(self, exc: BaseException, context: str) -> bool:
        key = f"{type(exc).__name__}:{context}"
        now = self.clock()
        last = self._last_sent.get(key)
        if last is not None and now - last < self.window_seconds:
            return False
        self._last_sent[key] = now
        return True
