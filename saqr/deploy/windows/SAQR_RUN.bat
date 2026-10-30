@echo off
chcp 65001 >nul
title SAQR v6.2.3 — صقر
cd /d "%~dp0..\.."
if not exist ".env" (
  if exist "saqr.env" copy /Y saqr.env .env >nul
)
if not exist ".env" (
  echo [ERROR] Missing .env — copy saqr.env.template to .env and fill keys.
  pause
  exit /b 1
)
if exist "scripts\sanitize_saqr_env.py" (
  python scripts\sanitize_saqr_env.py .env 2>nul
) else if exist "..\..\scripts\sanitize_saqr_env.py" (
  python ..\..\scripts\sanitize_saqr_env.py .env 2>nul
)
set PATH=%USERPROFILE%\.cargo\bin;%PATH%
if exist "target\release\saqr.exe" (
  target\release\saqr.exe
) else (
  echo Building SAQR v6.2.3...
  cargo build --release
  if errorlevel 1 pause & exit /b 1
  target\release\saqr.exe
)
pause
