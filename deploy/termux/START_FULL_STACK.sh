#!/data/data/com.termux/files/usr/bin/bash
# تشغيل Backend كامل في خلفية Termux (API + Tri-Commander bot + Discord اختياري)
set -euo pipefail

GS_ROOT="${GOLDENSHIELD_OFFICIAL_ROOT:-$HOME/goldenshield-ai}"
cd "$GS_ROOT"
export GOLDENSHIELD_OFFICIAL_ROOT="$GS_ROOT"
export PYTHONUNBUFFERED=1

# منع نوم الهاتف أثناء التشغيل (يتطلب: pkg install termux-api)
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock || true
fi

mkdir -p storage/runtime storage/logs

if [[ -f .env ]]; then
  eval "$(python3 - <<'PY'
from dotenv import dotenv_values
for k, v in (dotenv_values(".env") or {}).items():
    if k and v is not None:
        print(f"export {k}={v!r}")
PY
)"
fi

bash "$GS_ROOT/deploy/termux/STOP_STACK.sh" 2>/dev/null || true
sleep 1

PORT="${MOBILE_API_PORT:-8790}"
nohup python -m terminal_app.server >>storage/logs/mobile_api.log 2>&1 &
echo $! >storage/runtime/mobile_api.pid
sleep 2

if ! curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null; then
  echo "API_NOT_READY — tail storage/logs/mobile_api.log"
  exit 1
fi

nohup python main.py >>storage/logs/bot_stdout.log 2>&1 &
echo $! >storage/runtime/bot_main.pid

if [[ "${DISCORD_NOTIFY_ENABLED:-false}" != "false" && "${DISCORD_NOTIFY_ENABLED:-0}" != "0" ]]; then
  if [[ -f bridges/discord/discord_bridge.py ]]; then
    nohup python bridges/discord/discord_bridge.py >>storage/logs/discord_bridge.log 2>&1 &
    echo $! >storage/runtime/discord_bridge.pid
  fi
fi

echo "STACK_OK api=http://127.0.0.1:${PORT}/"
echo "APK: افتح GoldenShield-Control → http://127.0.0.1:${PORT}"
