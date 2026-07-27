from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from app.config import Config
from app.handlers import admin, game, safety, start, status
from app.logging_config import configure_logging
from app.services.admin_service import AdminService
from app.services.content_importer import ContentImporter
from app.services.game_service import GameService
from app.services.safety_service import SafetyService
from app.services.timer_service import TimerService
from app.storage import Database

logger = logging.getLogger(__name__)


def build_services(config: Config) -> tuple[Database, dict[str, object]]:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(config.database_path)
    db.apply_migrations()
    services: dict[str, object] = {
        "config": config,
        "db": db,
        "game_service": GameService(db, config),
        "safety_service": SafetyService(db),
        "timer_service": TimerService(db),
        "admin_service": AdminService(db),
    }
    return db, services


def build_dispatcher(services: dict[str, object]) -> Dispatcher:
    dp = Dispatcher(**services)
    dp.include_router(safety.router)
    dp.include_router(start.router)
    dp.include_router(status.router)
    dp.include_router(admin.router)
    dp.include_router(game.router)
    return dp


async def _heartbeat_loop(db: Database) -> None:
    while True:
        db.execute(
            """
            INSERT INTO app_heartbeats (component, status, details, updated_at)
            VALUES ('polling_bot', 'ok', '{}', CURRENT_TIMESTAMP)
            ON CONFLICT(component) DO UPDATE SET
                status = excluded.status,
                details = excluded.details,
                updated_at = CURRENT_TIMESTAMP
            """
        )
        await asyncio.sleep(30)


async def run_async() -> None:
    config = Config.from_env()
    configure_logging(config.log_level)
    config.validate_for_runtime()
    db, services = build_services(config)

    for seed_path in sorted(Path("content").glob("*.csv")):
        try:
            ContentImporter(db).import_file(seed_path, content_version=f"startup_seed:{seed_path.name}", dry_run=False)
        except Exception:
            logger.exception("startup seed import failed for %s", seed_path)

    if config.dry_run:
        logger.info("DRY_RUN=true; initialization completed without Telegram polling")
        db.close()
        return

    session = AiohttpSession(proxy=config.telegram_proxy_url) if config.telegram_proxy_url else None
    bot = Bot(
        token=config.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = build_dispatcher(services)
    timer_service = services["timer_service"]
    assert isinstance(timer_service, TimerService)
    heartbeat_task = asyncio.create_task(_heartbeat_loop(db))
    timer_task = asyncio.create_task(timer_service.run_due_loop(bot.send_message))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        heartbeat_task.cancel()
        timer_task.cancel()
        await bot.session.close()
        db.close()


def run() -> None:
    asyncio.run(run_async())
