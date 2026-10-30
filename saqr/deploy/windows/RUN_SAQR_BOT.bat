@echo off
chcp 65001 >nul
title SAQR Bot - صقر
cd /d C:\Saqr\Saqr
if not exist ".env" (
  echo [ERROR] Missing C:\Saqr\Saqr\.env
  pause
  exit /b 1
)
if exist "target\release\saqr.exe" (
  target\release\saqr.exe
) else if exist "saqr.exe" (
  saqr.exe
) else (
  echo [ERROR] saqr.exe not found. Re-upload binary to C:\Saqr\Saqr\
  pause
  exit /b 1
)
