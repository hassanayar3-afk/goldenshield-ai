@echo off
chcp 65001 >nul
echo إيقاف saqr.exe...
taskkill /IM saqr.exe /F >nul 2>&1
if errorlevel 1 (echo لا يوجد عملية saqr.exe نشطة.) else (echo تم الإيقاف.)
pause
