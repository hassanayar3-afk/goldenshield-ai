@echo off
title GoldenShield - فحص المجلد
cd /d "%~dp0"
echo Folder: %CD%
echo.
set OK=1
for %%F in (requirements.txt main.py .env config scripts) do (
  if exist %%F (
    echo [OK] %%F
  ) else (
    echo [MISSING] %%F
    set OK=0
  )
)
echo.
if "%OK%"=="1" (
  echo Folder is READY. Run 00_START.bat
) else (
  echo Folder is WRONG. Re-extract zip to C:\GoldenShield
)
pause
