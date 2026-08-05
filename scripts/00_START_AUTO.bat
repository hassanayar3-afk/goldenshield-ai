@echo off
rem DEPRECATED — كان يشغّل main.py مباشرة ويصارع المهمة الرسمية.
rem المسار الوحيد: START_BOT.bat → GoldenShieldBotOfficial → run_official_bot.ps1
cd /d "%~dp0.."
echo [GS] scripts\00_START_AUTO.bat deprecated — redirecting to START_BOT.bat
call "%~dp0..\START_BOT.bat"
