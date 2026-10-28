#!/data/data/com.termux/files/usr/bin/bash
# GoldenShield Terminal — تثبيت أولي على Termux (Android)
set -euo pipefail

GS_ROOT="${GOLDENSHIELD_OFFICIAL_ROOT:-$HOME/goldenshield-ai}"
export GS_ROOT

pkg update -y
pkg install -y python git curl termux-api

if [[ ! -d "$GS_ROOT/.git" ]]; then
  git clone --depth 1 -b cursor/win-remote-deploy-fix-2e26 \
    https://github.com/hassanayar3-afk/goldenshield-ai.git "$GS_ROOT" || {
    echo "CLONE_FAIL — استخدم فرعك أو انسخ المستودع يدوياً إلى $GS_ROOT"
    exit 1
  }
fi

cd "$GS_ROOT"
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p storage/runtime storage/logs storage/db

if [[ ! -f .env ]]; then
  cp config/env.production.template .env
  sed -i 's|GOLDENSHIELD_OFFICIAL_ROOT=.*|GOLDENSHIELD_OFFICIAL_ROOT='"$GS_ROOT"'|' .env 2>/dev/null || true
  sed -i 's|CLOUDFLARE_TUNNEL_ENABLED=.*|CLOUDFLARE_TUNNEL_ENABLED=false|' .env 2>/dev/null || true
fi

export GOLDENSHIELD_OFFICIAL_ROOT="$GS_ROOT"
echo "INSTALL_OK root=$GS_ROOT"
echo "NEXT: bash deploy/termux/START_FULL_STACK.sh"
