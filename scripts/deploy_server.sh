#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_REF="${1:-origin/main}"
APP_DIR="${APP_DIR:-/opt/tg_18_bot}"
REPO_URL="${REPO_URL:-https://github.com/NikitaZhilin/tg_18-_bot.git}"
SERVICE_NAME="${SERVICE_NAME:-tg-18-bot}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/tg-18-bot}"
LOCK_FILE="${LOCK_FILE:-/var/lock/tg-18-bot-deploy.lock}"

exec 9>"$LOCK_FILE"
flock -n 9 || {
  echo "Another deployment is already running."
  exit 1
}

if [ ! -d "$APP_DIR/.git" ]; then
  mkdir -p "$(dirname "$APP_DIR")"
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
git fetch --prune origin
TARGET_COMMIT="$(git rev-parse "$TARGET_REF^{commit}")"
PREVIOUS_COMMIT="$(git rev-parse HEAD)"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Tracked server files contain local changes; deployment stopped."
  exit 1
fi

STAGING_ROOT="$(mktemp -d /tmp/tg-18-bot-release.XXXXXX)"
STAGING_DIR="$STAGING_ROOT/worktree"
ROLLBACK_REQUIRED=0
BACKUP_PATH=""
DATABASE_PATH=""

cleanup() {
  git worktree remove --force "$STAGING_DIR" >/dev/null 2>&1 || true
  rm -rf "$STAGING_ROOT"
}

rollback() {
  echo "Deployment failed. Rolling back to $PREVIOUS_COMMIT."
  set +e
  systemctl stop "$SERVICE_NAME"
  if [ -n "$BACKUP_PATH" ] && [ -f "$BACKUP_PATH" ] && [ -n "$DATABASE_PATH" ]; then
    "$STAGING_DIR/.venv/bin/python" \
      "$STAGING_DIR/scripts/restore_database.py" "$BACKUP_PATH" "$DATABASE_PATH"
  fi
  git checkout --detach "$PREVIOUS_COMMIT"
  .venv/bin/python -m pip install -r requirements.txt
  systemctl restart "$SERVICE_NAME"
  systemctl status "$SERVICE_NAME" --no-pager
}

on_exit() {
  exit_code=$?
  if [ "$exit_code" -ne 0 ] && [ "$ROLLBACK_REQUIRED" -eq 1 ]; then
    rollback
  fi
  cleanup
  trap - EXIT
  exit "$exit_code"
}
trap on_exit EXIT

git worktree add --detach "$STAGING_DIR" "$TARGET_COMMIT"
python3 -m venv "$STAGING_DIR/.venv"
"$STAGING_DIR/.venv/bin/python" -m pip install --upgrade pip
"$STAGING_DIR/.venv/bin/python" -m pip install -r "$STAGING_DIR/requirements-dev.txt"
(
  cd "$STAGING_DIR"
  export DRY_RUN=true
  export ALLOW_UNLISTED_USERS=true
  export ALLOWED_TELEGRAM_USER_IDS=111,222
  export DATA_DIR="$STAGING_DIR/.tmp/data"
  export DATABASE_PATH="$STAGING_DIR/.tmp/data/check.sqlite3"
  .venv/bin/python scripts/audit_card_content.py
  .venv/bin/python scripts/import_cards.py --check content/cards.csv
  .venv/bin/python scripts/import_cards.py --check content/restricted_cards.csv
  .venv/bin/python scripts/smoke_start.py
  .venv/bin/python -m pytest --basetemp "$STAGING_DIR/.pytest-tmp"
)

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created $APP_DIR/.env; fill BOT_TOKEN and user IDs before starting."
  exit 1
fi

mkdir -p data "$BACKUP_DIR"
CURRENT_PYTHON=".venv/bin/python"
if [ ! -x "$CURRENT_PYTHON" ]; then
  CURRENT_PYTHON="python3"
fi
DATABASE_PATH="$("$CURRENT_PYTHON" -c \
  'from app.config import Config; print(Config.from_env().database_path.resolve())')"
if [ -f "$DATABASE_PATH" ]; then
  BACKUP_PATH="$BACKUP_DIR/bot-$(date -u +%Y%m%dT%H%M%SZ)-$PREVIOUS_COMMIT.sqlite3"
  "$STAGING_DIR/.venv/bin/python" \
    "$STAGING_DIR/scripts/backup_database.py" "$DATABASE_PATH" "$BACKUP_PATH"
fi

ROLLBACK_REQUIRED=1
git checkout --detach "$TARGET_COMMIT"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

cat >"/etc/systemd/system/$SERVICE_NAME.service" <<SERVICE
[Unit]
Description=Telegram private card game bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/python -m app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl stop "$SERVICE_NAME" || true
.venv/bin/python scripts/migrate_database.py
DEPLOYED_AT="$(date -u +%s)"
systemctl restart "$SERVICE_NAME"

healthy=0
for _ in $(seq 1 18); do
  if systemctl is-active --quiet "$SERVICE_NAME" \
    && .venv/bin/python scripts/health_check.py \
      "$DATABASE_PATH" --max-age 90 --updated-after "$DEPLOYED_AT"; then
    healthy=1
    break
  fi
  sleep 5
done
if [ "$healthy" -ne 1 ]; then
  journalctl -u "$SERVICE_NAME" -n 100 --no-pager
  exit 1
fi

find "$BACKUP_DIR" -type f -name 'bot-*.sqlite3' -mtime +14 -delete
ROLLBACK_REQUIRED=0
echo "Deployment completed: $TARGET_COMMIT"
systemctl status "$SERVICE_NAME" --no-pager
