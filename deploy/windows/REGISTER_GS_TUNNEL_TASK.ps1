param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Stop"
$script = Join-Path $Root "deploy\windows\GS_TUNNEL_KEEPALIVE.ps1"
if (-not (Test-Path $script)) { throw "Missing $script" }
$taskName = "GoldenShieldTunnel"
Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "GS_TUNNEL_KEEPALIVE"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument (
    "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Root `"$Root`""
)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger (New-ScheduledTaskTrigger -AtLogon) -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "TUNNEL_TASK_OK"
