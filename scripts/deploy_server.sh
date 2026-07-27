#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/tg_18_bot}"
REPO_URL="${REPO_URL:-https://github.com/NikitaZhilin/tg_18-_bot.git}"

if [ ! -d "$APP_DIR/.git" ]; then
  mkdir -p "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
git pull --ff-only
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
mkdir -p data

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created $APP_DIR/.env; fill BOT_TOKEN and user IDs before starting."
fi

cat >/etc/systemd/system/tg-18-bot.service <<SERVICE
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
systemctl enable tg-18-bot
systemctl restart tg-18-bot
systemctl status tg-18-bot --no-pager
