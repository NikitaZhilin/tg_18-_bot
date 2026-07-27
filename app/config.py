from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _parse_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part:
            ids.add(int(part))
    return ids


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_user_ids: set[int]
    admin_user_ids: set[int]
    player_1_name: str
    player_2_name: str
    bot_timezone: str
    data_dir: Path
    database_path: Path
    log_level: str
    dry_run: bool
    allow_unlisted_users: bool
    allow_level_4_default: bool
    telegram_proxy_url: str | None

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> "Config":
        _load_dotenv(Path(env_file))
        data_dir = Path(os.getenv("DATA_DIR", "./data"))
        database_path = Path(os.getenv("DATABASE_PATH", str(data_dir / "bot.sqlite3")))
        admin_ids = _parse_ids(os.getenv("ADMIN_TELEGRAM_USER_IDS"))
        allowed_ids = _parse_ids(os.getenv("ALLOWED_TELEGRAM_USER_IDS"))
        if not admin_ids:
            admin_ids = set(allowed_ids)
        return cls(
            bot_token=os.getenv("BOT_TOKEN", "").strip(),
            allowed_user_ids=allowed_ids,
            admin_user_ids=admin_ids,
            player_1_name=os.getenv("PLAYER_1_NAME", "Player 1"),
            player_2_name=os.getenv("PLAYER_2_NAME", "Player 2"),
            bot_timezone=os.getenv("BOT_TIMEZONE", "Europe/Moscow"),
            data_dir=data_dir,
            database_path=database_path,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            dry_run=_parse_bool(os.getenv("DRY_RUN"), False),
            allow_unlisted_users=_parse_bool(os.getenv("ALLOW_UNLISTED_USERS"), False),
            allow_level_4_default=_parse_bool(os.getenv("ALLOW_LEVEL_4_DEFAULT"), False),
            telegram_proxy_url=os.getenv("TELEGRAM_PROXY_URL") or None,
        )

    def is_allowed(self, user_id: int) -> bool:
        return self.allow_unlisted_users or user_id in self.allowed_user_ids

    def is_admin(self, user_id: int) -> bool:
        return self.is_allowed(user_id) and user_id in self.admin_user_ids

    def validate_for_runtime(self) -> None:
        if not self.dry_run and not self.bot_token:
            raise RuntimeError("BOT_TOKEN is required unless DRY_RUN=true")
        if not self.allow_unlisted_users and not self.allowed_user_ids:
            raise RuntimeError("ALLOWED_TELEGRAM_USER_IDS is required")
