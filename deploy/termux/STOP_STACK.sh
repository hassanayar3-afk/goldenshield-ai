#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
GS_ROOT="${GOLDENSHIELD_OFFICIAL_ROOT:-$HOME/goldenshield-ai}"
cd "$GS_ROOT" 2>/dev/null || exit 0

for f in storage/runtime/mobile_api.pid storage/runtime/bot_main.pid storage/runtime/discord_bridge.pid; do
  if [[ -f "$f" ]]; then
    kill "$(cat "$f")" 2>/dev/null || true
    rm -f "$f"
  fi
done

pkill -f "terminal_app.server" 2>/dev/null || true
pkill -f "main.py" 2>/dev/null || true
pkill -f "discord_bridge.py" 2>/dev/null || true

if command -v termux-wake-unlock >/dev/null 2>&1; then
  termux-wake-unlock || true
fi
echo "STOP_OK"
