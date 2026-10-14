from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import ErrorEvent

from app.config import Config
from app.services.error_report import USER_ERROR_TEXT, ReportThrottle, build_admin_report

logger = logging.getLogger(__name__)

_throttle = ReportThrottle()


def _context(event: ErrorEvent) -> str:
    update = event.update
    if update.callback_query:
        return f"кнопка {update.callback_query.data!r}"
    if update.message:
        text = update.message.text or ""
        if text.startswith("/"):
            return f"команда {text.split()[0]!r}"
        return "сообщение"
    return update.event_type or "обновление"


async def on_error(event: ErrorEvent, bot: Bot, config: Config) -> bool:
    exc = event.exception
    context = _context(event)
    logger.exception("unhandled error in %s", context, exc_info=exc)

    update = event.update
    try:
        if update.callback_query:
            # Stops the endless spinner on the pressed button.
            await update.callback_query.answer(USER_ERROR_TEXT, show_alert=True)
        elif update.message:
            await update.message.answer(USER_ERROR_TEXT)
    except Exception:
        logger.warning("could not tell the user about the error", exc_info=True)

    if _throttle.should_send(exc, context):
        report = build_admin_report(exc, context)
        for admin_id in sorted(config.admin_user_ids):
            try:
                await bot.send_message(admin_id, report, parse_mode=None)
            except Exception:
                logger.warning("could not send error report to admin %s", admin_id, exc_info=True)
    return True
