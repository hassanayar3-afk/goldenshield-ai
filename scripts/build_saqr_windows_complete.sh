#!/usr/bin/env bash
# Build Saqr-Windows-Complete-v6.2.3-bridge.zip (full runtime layout)
# Usage:
#   ./scripts/build_saqr_windows_complete.sh           → GitHub-safe (env.template placeholders only)
#   ./scripts/build_saqr_windows_complete.sh --with-env → includes saqr/.env (NEVER upload to public GitHub)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SAQR="$ROOT/saqr"
INCLUDE_ENV=false
if [[ "${1:-}" == "--with-env" ]]; then
  INCLUDE_ENV=true
fi

OUT_NAME="Saqr-Windows-Complete-v6.2.3-bridge"
if $INCLUDE_ENV; then
  OUT_NAME="Saqr-Windows-Complete-v6.2.3-bridge-configured"
fi
STAGE="/tmp/${OUT_NAME}"
ZIP="/tmp/${OUT_NAME}.zip"

ENV_SRC=""
for candidate in "$SAQR/.env" "$ROOT/saqr/.env" "$SAQR/saqr.env"; do
  if [[ -f "$candidate" ]]; then
    ENV_SRC="$candidate"
    break
  fi
done

if $INCLUDE_ENV && [[ -z "$ENV_SRC" ]]; then
  echo "[FAIL] --with-env requires saqr/.env on disk" >&2
  exit 1
fi

rm -rf "$STAGE" "$ZIP"
mkdir -p "$STAGE"/{bin,data,logs,scripts,web/control_terminal}

echo "[build] cross-compile saqr.exe..."
(cd "$SAQR" && cargo build --release --target x86_64-pc-windows-gnu)
cp "$SAQR/target/x86_64-pc-windows-gnu/release/saqr.exe" "$STAGE/bin/"

cp "$SAQR/web/control_terminal/index.html" "$SAQR/web/control_terminal/dashboard.js" "$STAGE/web/control_terminal/"
cp "$ROOT/scripts/sanitize_saqr_env.py" "$ROOT/scripts/validate_saqr_env.py" "$STAGE/scripts/"

if $INCLUDE_ENV; then
  # No blank lines: drop empty lines, keep KEY= even if value empty (e.g. TELEGRAM_SECONDARY_BOT_TOKEN=)
  awk 'NF || /^[[:space:]]*#/' "$ENV_SRC" | sed '/^[[:space:]]*$/d' > "$STAGE/.env"
  cp "$STAGE/.env" "$STAGE/saqr.env"
  echo "[pack] embedded .env from $ENV_SRC (Binance + Telegram — local build only)"
else
  cp "$ROOT/saqr.env.template" "$STAGE/env.template"
  sed '/^[[:space:]]*$/d' "$ROOT/saqr.env.template" > "$STAGE/env.template"
  echo "[pack] env.template only (public release — fill .env on your PC)"
fi

cat > "$STAGE/SAQR_RUN.bat" << 'BAT'
@echo off
setlocal EnableExtensions
chcp 65001 >nul
title SAQR Engine v6.2.3 — صقر
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   SAQR v6.2.3 — Paper + Telegram Bridge   ║
echo  ╚══════════════════════════════════════════╝
echo.

if not exist ".env" (
  if exist "saqr.env" copy /Y saqr.env .env >nul
)
if not exist ".env" (
  if exist "env.template" copy /Y env.template .env >nul
  echo [OK] Created .env from env.template
)
if not exist ".env" (
  echo [ERROR] Missing .env in: %CD%
  pause
  exit /b 1
)

if exist "FIX_MY_ENV.bat" call FIX_MY_ENV.bat

if exist "scripts\validate_saqr_env.py" (
  where python >nul 2>&1
  if not errorlevel 1 python scripts\validate_saqr_env.py .env
  if errorlevel 1 pause & exit /b 1
)

if exist "bin\saqr.exe" (
  echo [CHECK] Engine preflight...
  "bin\saqr.exe" --check
  if errorlevel 1 pause & exit /b 1
  echo [RUN] Dashboard: http://127.0.0.1:8788
  echo       Paper 5000 USD ^| api.binance.com ^| Telegram bridge
  "bin\saqr.exe"
  goto :done
)

echo [ERROR] bin\saqr.exe not found.
pause
exit /b 1

:done
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" echo [EXIT] Code %EC%
pause
exit /b %EC%
BAT

cat > "$STAGE/FIX_MY_ENV.bat" << 'BAT'
@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".env" if exist "saqr.env" copy /Y saqr.env .env
if not exist ".env" if exist "env.template" copy /Y env.template .env
if not exist ".env" (
  echo Create .env first.
  pause
  exit /b 1
)
where python >nul 2>&1
if errorlevel 1 exit /b 0
if exist "scripts\sanitize_saqr_env.py" python scripts\sanitize_saqr_env.py .env
echo OK — .env ready.
exit /b 0
BAT

cat > "$STAGE/OPEN_DASHBOARD.bat" << 'BAT'
@echo off
start http://127.0.0.1:8788
BAT

cat > "$STAGE/SAQR_CHECK.bat" << 'BAT'
@echo off
cd /d "%~dp0"
if exist "bin\saqr.exe" ("bin\saqr.exe" --check & pause) else (echo Missing bin\saqr.exe & pause)
BAT

if $INCLUDE_ENV; then
  READ_ME='SAQR v6.2.3 — حزمة جاهزة (.env مكتمل)
========================================
1) فك الضغط
2) شغّل SAQR_RUN.bat مباشرة (ملف .env موجود ومربوط)
3) OPEN_DASHBOARD.bat أو http://127.0.0.1:8788
لا تشارك هذا المجلد — يحتوي مفاتيحك.'
else
  READ_ME='SAQR v6.2.3 — حزمة Windows
========================================
1) فك الضغط
2) انسخ env.template إلى .env وعبّئ Telegram + Binance
3) SAQR_RUN.bat'
fi

printf '%s\n' "$READ_ME" > "$STAGE/ابدأ_هنا.txt"

touch "$STAGE/data/.keep" "$STAGE/logs/.keep"

(cd /tmp && zip -r "$ZIP" "$OUT_NAME")
echo "PACKAGE_READY $ZIP ($(du -h "$ZIP" | cut -f1))"

if $INCLUDE_ENV; then
  cp "$ZIP" /opt/cursor/artifacts/"${OUT_NAME}.zip"
  echo "[artifact] configured zip (with .env) → /opt/cursor/artifacts/${OUT_NAME}.zip"
else
  cp "$ZIP" "$ROOT/storage/${OUT_NAME}.zip" 2>/dev/null || mkdir -p "$ROOT/storage" && cp "$ZIP" "$ROOT/storage/${OUT_NAME}.zip"
  cp "$ZIP" /opt/cursor/artifacts/"${OUT_NAME}.zip" 2>/dev/null || true
fi
