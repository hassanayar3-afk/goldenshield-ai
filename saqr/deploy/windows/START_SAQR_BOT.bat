@echo off
chcp 65001 >nul
title SAQR Bot - صقر
cd /d "%~dp0.."
if not exist ".env" (
  echo [ERROR] Missing .env next to Saqr folder. Copy saqr.env to C:\Saqr\Saqr\.env
  pause
  exit /b 1
)
set PATH=%USERPROFILE%\.cargo\bin;%PATH%
if exist "target\release\saqr.exe" (
  echo Starting SAQR release binary...
  target\release\saqr.exe
) else (
  echo Building SAQR (first run may take several minutes)...
  cargo build --release
  if errorlevel 1 exit /b 1
  target\release\saqr.exe
)
