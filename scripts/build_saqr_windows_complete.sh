#!/usr/bin/env bash
# Build Saqr-Windows-Complete-v6.2.3-bridge.zip (full runtime layout)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SAQR="$ROOT/saqr"
OUT_NAME="Saqr-Windows-Complete-v6.2.3-bridge"
STAGE="/tmp/${OUT_NAME}"
ZIP="/tmp/${OUT_NAME}.zip"

rm -rf "$STAGE" "$ZIP"
mkdir -p "$STAGE"/{bin,data,logs,scripts,web/control_terminal}

echo "[build] cross-compile saqr.exe..."
(cd "$SAQR" && cargo build --release --target x86_64-pc-windows-gnu)
cp "$SAQR/target/x86_64-pc-windows-gnu/release/saqr.exe" "$STAGE/bin/"

cp "$SAQR/web/control_terminal/index.html" "$SAQR/web/control_terminal/dashboard.js" "$STAGE/web/control_terminal/"
cp "$ROOT/scripts/sanitize_saqr_env.py" "$ROOT/scripts/validate_saqr_env.py" "$STAGE/scripts/"
cp "$ROOT/saqr.env.template" "$STAGE/env.template"

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
  echo [OK] Created .env from env.template — add TELEGRAM_* keys.
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

if exist "target\release\saqr.exe" (
  "target\release\saqr.exe"
  goto :done
)

set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
if exist "Cargo.toml" (
  cargo build --release
  if errorlevel 1 pause & exit /b 1
  "target\release\saqr.exe"
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
if not exist ".env" if exist "env.template" copy /Y env.template .env
if not exist ".env" (
  echo Create .env first.
  pause
  exit /b 1
)
where python >nul 2>&1
if errorlevel 1 (
  echo Python 3 recommended for env sanitizer — skipping.
  exit /b 0
)
if exist "scripts\sanitize_saqr_env.py" (
  python scripts\sanitize_saqr_env.py .env
)
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

cat > "$STAGE/ابدأ_هنا.txt" << 'TXT'
SAQR v6.2.3-bridge — حزمة Windows الكاملة
==========================================
1) فك الضغط في مجلد (مثل C:\Saqr)
2) انسخ env.template إلى .env (أو شغّل SAQR_RUN.bat لإنشائه)
3) عدّل .env: TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID (مطلوب للجسر)
4) شغّل FIX_MY_ENV.bat (اختياري — يحتاج Python)
5) شغّل SAQR_RUN.bat
6) افتح OPEN_DASHBOARD.bat أو http://127.0.0.1:8788

المحتويات:
  bin\saqr.exe          — المحرك
  web\control_terminal  — لوحة التحكم
  scripts\              — تنظيف .env
  data\ logs\           — سجلات التشغيل

SAQR_MODE=paper — تنفيذ محلي 5000$ + أسعار حية من api.binance.com
TXT

touch "$STAGE/data/.keep" "$STAGE/logs/.keep"

(cd /tmp && zip -r "$ZIP" "$OUT_NAME")
echo "PACKAGE_READY $ZIP ($(du -h "$ZIP" | cut -f1))"
cp "$ZIP" "$ROOT/storage/${OUT_NAME}.zip" 2>/dev/null || mkdir -p "$ROOT/storage" && cp "$ZIP" "$ROOT/storage/${OUT_NAME}.zip"
cp "$ZIP" /opt/cursor/artifacts/"${OUT_NAME}.zip" 2>/dev/null || true
