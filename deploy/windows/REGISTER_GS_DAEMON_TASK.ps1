# Long-running gs_daemon via Scheduled Task (survives WinRM / short GS_START exit)
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Stop"
$daemon = Join-Path $Root "gs_daemon.ps1"
if (-not (Test-Path $daemon)) { throw "Missing $daemon" }
$taskName = "GoldenShieldDaemon"
Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "gs_daemon\.ps1"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument (
    "-NoProfile -ExecutionPolicy Bypass -File `"$daemon`" -Root `"$Root`""
)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger (New-ScheduledTaskTrigger -AtLogon) -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "DAEMON_TASK_OK"
