"""Weekly off-server copy: sends a fresh SQLite backup to the owners in Telegram.

Run by the tg-18-bot-offsite.timer systemd unit. Sends only to ADMIN_TELEGRAM_USER_IDS
and refuses to run if there are more than MAX_RECIPIENTS of them, so the database can
never be sent to a wide audience by a config mistake.
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Config  # noqa: E402
from scripts.scheduled_backup import make_backup  # noqa: E402

MAX_RECIPIENTS = 3
TELEGRAM_FILE_LIMIT = 49 * 1024 * 1024


def recipients(config: Config) -> list[int]:
    ids = sorted(config.admin_user_ids)
    if not ids:
        raise SystemExit("ADMIN_TELEGRAM_USER_IDS is empty: nobody to send the backup to")
    if len(ids) > MAX_RECIPIENTS:
        raise SystemExit(f"refusing to send the database to {len(ids)} recipients (max {MAX_RECIPIENTS})")
    return ids


def caption(now: datetime) -> str:
    return (
        f"Резервная копия базы бота за {now:%d.%m.%Y %H:%M} (МСК).\n"
        "Файл не пересылайте: в нём вся история игры. Сохраните его в надёжном месте."
    )


def build_archive(database: Path, workdir: Path, now: datetime) -> Path:
    raw = make_backup(database, workdir, keep_days=0, now=now)
    archive = workdir / f"tg18-backup-{now:%Y%m%d-%H%M}.sqlite3.gz"
    with raw.open("rb") as src, gzip.open(archive, "wb") as dst:
        shutil.copyfileobj(src, dst)
    raw.unlink(missing_ok=True)
    if archive.stat().st_size > TELEGRAM_FILE_LIMIT:
        raise SystemExit("backup is larger than the Telegram bot file limit")
    return archive


async def send(config: Config, archive: Path, text: str, chat_ids: list[int]) -> int:
    from aiogram import Bot
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.types import FSInputFile

    session = AiohttpSession(proxy=config.telegram_proxy_url) if config.telegram_proxy_url else None
    bot = Bot(token=config.bot_token, session=session)
    failures = 0
    try:
        for chat_id in chat_ids:
            try:
                await bot.send_document(
                    chat_id,
                    FSInputFile(archive),
                    caption=text,
                    disable_notification=True,
                )
            except Exception as exc:  # report and continue with other owners
                failures += 1
                print(f"send failed for one recipient: {type(exc).__name__}: {exc}", file=sys.stderr)
    finally:
        await bot.session.close()
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()

    config = Config.from_env(args.env_file)
    chat_ids = recipients(config)
    if not config.bot_token:
        raise SystemExit("BOT_TOKEN is empty")
    now = datetime.now(ZoneInfo(config.bot_timezone))
    with tempfile.TemporaryDirectory(prefix="tg18-offsite-") as tmp:
        archive = build_archive(config.database_path, Path(tmp), now)
        failures = asyncio.run(send(config, archive, caption(now), chat_ids))
    print(f"offsite backup sent to {len(chat_ids) - failures} of {len(chat_ids)} owners")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
