@echo off
title GoldenShield Laptop One-Shot
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\windows\GOLDENSHIELD_LAPTOP_ONE_SHOT.ps1" -Root "%~dp0"
if errorlevel 2 (
  echo.
  echo Complete .env then double-click this file again.
  pause
)
if errorlevel 1 pause
