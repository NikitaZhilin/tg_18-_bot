#!/usr/bin/env bash
# Runs scripts/server_health.sh on the server over SSH and turns its output into
# GitHub annotations. The repository is public: output is masked again here.
set -uo pipefail

for name in DEPLOY_HOST DEPLOY_USER SSHPASS; do
  if [ -z "${!name:-}" ]; then
    echo "::error title=Server health::secret for $name is not set"
    exit 1
  fi
done
port="${DEPLOY_PORT:-22}"
mkdir -p "$HOME/.ssh"
ssh-keyscan -p "$port" -H "$DEPLOY_HOST" >> "$HOME/.ssh/known_hosts" 2>/dev/null

report="$(sshpass -e ssh -p "$port" -o BatchMode=no -o StrictHostKeyChecking=yes \
  "$DEPLOY_USER@$DEPLOY_HOST" "bash -s" < scripts/server_health.sh 2>&1)"
status=$?
report="$(printf '%s\n' "$report" | sed -E 's/[0-9]{5,}/<id>/g; s/[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/<ip>/g')"

escape() { sed -e 's/%/%25/g' | awk 'BEGIN{ORS="%0A"} {print}'; }
echo "::notice title=Server health::$(printf '%s\n' "$report" | escape)"
printf '%s\n' "$report" | grep '^WARN:' | while IFS= read -r line; do
  echo "::warning title=Server health::$(printf '%s' "${line#WARN: }" | escape)"
done
if [ "$status" -ne 0 ]; then
  echo "::error title=Server health::SSH check failed with exit code $status"
  exit "$status"
fi
