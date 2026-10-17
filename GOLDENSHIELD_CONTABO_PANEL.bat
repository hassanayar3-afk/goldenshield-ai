@echo off
title GoldenShield Contabo Panel Only
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\windows\GOLDENSHIELD_CONTABO_PANEL_ONE_SHOT.ps1" -Root "C:\GoldenShield_Binance"
pause
