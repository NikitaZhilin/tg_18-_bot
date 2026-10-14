#!/usr/bin/env bash
# Read-only server check. Changes nothing. Prints "KEY: value" lines and "WARN: ..." for problems.
# The repository is public, so output is technical only: no Telegram ids, texts or game statistics.
set -uo pipefail

APP_DIR="${APP_DIR:-/opt/tg_18_bot}"
SERVICE_NAME="${SERVICE_NAME:-tg-18-bot}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/tg-18-bot}"

mask() { sed -E 's/[0-9]{5,}/<id>/g'; }

echo "CHECKED_AT: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "LOAD: $(cut -d' ' -f1-3 /proc/loadavg)"
free -m | awk '/^Mem:/ {print "MEM_AVAILABLE_MB: " $7 " of " $2} /^Swap:/ {print "SWAP_USED_MB: " $3 " of " $2}'
df -P / | awk 'NR==2 {print "DISK_ROOT: " $5 " used, " int($4/1048576) " GB free"; if ($5+0 >= 90) print "WARN: root disk is " $5 " full"}'

if [ -d "$APP_DIR/.git" ]; then
  echo "DEPLOYED_COMMIT: $(git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null)"
else
  echo "WARN: $APP_DIR is not a git checkout"
fi

state="$(systemctl is-active "$SERVICE_NAME" 2>/dev/null)"
echo "SERVICE: $state"
[ "$state" = "active" ] || echo "WARN: service $SERVICE_NAME is $state"
echo "SERVICE_SINCE: $(systemctl show "$SERVICE_NAME" -p ActiveEnterTimestamp --value 2>/dev/null)"
restarts="$(systemctl show "$SERVICE_NAME" -p NRestarts --value 2>/dev/null)"
echo "SERVICE_RESTARTS: ${restarts:-?}"
[ "${restarts:-0}" -gt 3 ] 2>/dev/null && echo "WARN: service restarted $restarts times (crash loop?)"

instances="$(pgrep -fc "$APP_DIR/.venv/bin/python -m app" 2>/dev/null || true)"
echo "BOT_PROCESSES: ${instances:-0}"
[ "${instances:-0}" -gt 1 ] && echo "WARN: more than one bot process on this server"

journal="$(journalctl -u "$SERVICE_NAME" --since "24 hours ago" --no-pager -o cat 2>/dev/null)"
errors="$(printf '%s\n' "$journal" | grep -cE ' (ERROR|CRITICAL) ' || true)"
conflicts="$(printf '%s\n' "$journal" | grep -c 'TelegramConflictError' || true)"
network="$(printf '%s\n' "$journal" | grep -cE 'TelegramNetworkError|Failed to fetch updates' || true)"
echo "LOG_ERRORS_24H: $errors"
echo "LOG_GETUPDATES_CONFLICTS_24H: $conflicts"
echo "LOG_NETWORK_ERRORS_24H: $network"
[ "$conflicts" -gt 0 ] && echo "WARN: another bot instance uses the same token (getUpdates conflict)"
[ "$network" -gt 20 ] && echo "WARN: frequent Telegram network errors (proxy or hosting block?)"
if [ "$errors" -gt 0 ]; then
  echo "ERROR_KINDS_24H:"
  printf '%s\n' "$journal" | grep -E ' (ERROR|CRITICAL) ' \
    | sed -E 's/^[0-9-]+ [0-9:,]+ //' | cut -c1-120 | mask | sort | uniq -c | sort -rn | head -5
fi

backups="$(find "$BACKUP_DIR" -maxdepth 1 -name '*.sqlite3' 2>/dev/null | wc -l)"
echo "BACKUPS: $backups"
newest="$(ls -1t "$BACKUP_DIR"/*.sqlite3 2>/dev/null | head -1)"
if [ -n "$newest" ]; then
  age_h=$(( ( $(date +%s) - $(stat -c %Y "$newest") ) / 3600 ))
  echo "NEWEST_BACKUP_AGE_HOURS: $age_h"
  [ "$age_h" -gt 36 ] && echo "WARN: newest backup is $age_h hours old"
else
  echo "WARN: no backups in $BACKUP_DIR"
fi
timer_state="$(systemctl is-active "$SERVICE_NAME-backup.timer" 2>/dev/null)"
echo "BACKUP_TIMER: $timer_state"
[ "$timer_state" = "active" ] || echo "WARN: daily backup timer is not active"

PY="$APP_DIR/.venv/bin/python"
[ -x "$PY" ] || PY=python3
DB_PATH="$(cd "$APP_DIR" 2>/dev/null && "$PY" -c 'from app.config import Config; print(Config.from_env().database_path.resolve())' 2>/dev/null)"
if [ -z "$DB_PATH" ] || [ ! -f "$DB_PATH" ]; then
  echo "WARN: database not found"
  exit 0
fi
"$PY" - "$DB_PATH" <<'PY' 2>&1 | mask
import sqlite3
import sys

conn = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True)


def one(sql):
    try:
        row = conn.execute(sql).fetchone()
        return row[0] if row else None
    except sqlite3.Error as exc:
        return "error: %s" % exc


age = one("SELECT CAST((julianday('now') - julianday(updated_at)) * 86400 AS INTEGER) FROM app_heartbeats WHERE component = 'polling_bot'")
print("HEARTBEAT_AGE_SECONDS: %s" % age)
if not isinstance(age, int) or age > 120:
    print("WARN: heartbeat is stale or missing")
print("MIGRATION: %s" % one("SELECT name FROM schema_migrations ORDER BY name DESC LIMIT 1"))
print("DB_INTEGRITY: %s" % one("PRAGMA quick_check"))
failed = one("SELECT COUNT(*) FROM timers WHERE status = 'expired' AND started_at >= datetime('now', '-7 days')")
stuck = one("SELECT COUNT(*) FROM timers WHERE status = 'active' AND deadline_at < strftime('%Y-%m-%dT%H:%M:%S', 'now', '-10 minutes')")
print("TIMER_DELIVERY_FAILED_7D: %s" % failed)
print("TIMER_OVERDUE_NOW: %s" % stuck)
if isinstance(failed, int) and failed:
    print("WARN: %s timer notifications could not be delivered in 7 days" % failed)
if isinstance(stuck, int) and stuck:
    print("WARN: %s timers are overdue and not delivered" % stuck)
open_reports = one("SELECT COUNT(*) FROM card_feedback WHERE status = 'new'")
print("UNCLEAR_CARD_REPORTS_OPEN: %s" % open_reports)
PY
