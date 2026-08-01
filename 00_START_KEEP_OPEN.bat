@echo off
REM يشغّل START داخل نافذة تبقى مفتوحة دائماً حتى لو حدث خطأ
cd /d "%~dp0"
title GoldenShield Launcher
cmd /k "cd /d \"%~dp0\" && call 00_START.bat"
