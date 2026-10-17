#!/usr/bin/env bash
# يحدّث رابط السيرفر الافتراضي داخل APK قبل البناء
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/config/mobile_default_servers.txt"
DST="$ROOT/mobile_android/app/src/main/assets/default_servers.txt"
mkdir -p "$(dirname "$DST")"
if [[ -f "$ROOT/storage/runtime/mobile_tunnel_url.txt" ]]; then
  TUN=$(tr -d '\r\n' <"$ROOT/storage/runtime/mobile_tunnel_url.txt")
  if [[ "$TUN" == https://* ]]; then
    { echo "$TUN"; grep -v '^#' "$SRC" | grep -v '^$' | grep -v trycloudflare || true; } >"$DST"
    exit 0
  fi
fi
grep -v '^#' "$SRC" | grep -v '^$' >"$DST"
