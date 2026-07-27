from __future__ import annotations

import logging


PRIVATE_LOGGER_NAMES = ("aiogram.event", "aiogram.dispatcher")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    for name in PRIVATE_LOGGER_NAMES:
        logging.getLogger(name).setLevel(logging.WARNING)
