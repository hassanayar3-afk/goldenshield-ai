# Register GoldenShield watchdog (every 5 minutes)
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Stop"
$script = Join-Path $Root "deploy\windows\GS_WATCHDOG.ps1"
if (-not (Test-Path $script)) { throw "Missing $script" }
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Root `"$Root`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration ([TimeSpan]::MaxValue)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "GoldenShieldWatchdog" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Output "WATCHDOG_TASK_OK"
