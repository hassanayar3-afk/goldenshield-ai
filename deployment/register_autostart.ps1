# تسجيل تشغيل GoldenShield تلقائياً عند بدء Windows
# يشغّل: قاعدة البيانات + MT5 + بوت الإشارات (main.py عبر 00_START.bat)
# شغّل كمسؤول: INSTALL_AUTOSTART.bat

$ErrorActionPreference = "Stop"
$TaskName = "GoldenShield_WindowsBoot"
$ProjectPath = Split-Path -Parent $PSScriptRoot
$BootBat = Join-Path $ProjectPath "scripts\WINDOWS_BOOT.bat"

if (-not (Test-Path $BootBat)) {
    Write-Error "WINDOWS_BOOT.bat not found at $BootBat"
    exit 1
}

$Action = New-ScheduledTaskAction `
    -Execute $BootBat `
    -WorkingDirectory $ProjectPath

# عند بدء Windows (حتى بدون تسجيل دخول RDP) + عند تسجيل الدخول
$TriggerBoot = New-ScheduledTaskTrigger -AtStartup -RandomDelay (New-TimeSpan -Seconds 90)
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Days 365)

$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger @($TriggerBoot, $TriggerLogon) `
    -Settings $Settings `
    -Principal $Principal `
    -Description "GoldenShield: DB + MT5 + signal bot auto-start" `
    -Force | Out-Null

Write-Host "Registered task: $TaskName"
Write-Host "Boot script: $BootBat"
Write-Host "On Windows start: database, MT5, and signal bot will launch automatically."
