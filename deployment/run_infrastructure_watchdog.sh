#!/bin/bash
# تشغيل مراقب البنية — cron كل 5 دقائق على Contabo (يستخدم docker من السيرفر)
set -euo pipefail
cd /opt/goldenshield
mkdir -p storage/logs

DOCKER_BIN="$(command -v docker || true)"
if [ -z "$DOCKER_BIN" ]; then
  echo "docker CLI missing on host" >> storage/logs/watchdog.log
  exit 1
fi

/usr/bin/docker run --rm \
  --env-file /opt/goldenshield/.env \
  -e WATCHDOG_ENABLED \
  -e WATCHDOG_CHAT_ID \
  -e WATCHDOG_WINDOWS_HOST \
  -e WATCHDOG_WINDOWS_PORT \
  -e WATCHDOG_CONTAINER \
  -e WATCHDOG_STALE_MINUTES \
  -e WATCHDOG_REMIND_HOURS \
  -e WATCHDOG_CHECK_WINDOWS \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$DOCKER_BIN:/usr/bin/docker:ro" \
  -v /opt/goldenshield/storage:/app/storage \
  --entrypoint python \
  goldenshield-goldenshield:latest \
  -m operations.infrastructure_watchdog \
  >> /opt/goldenshield/storage/logs/watchdog.log 2>&1
