# Start full stack via Scheduled Task (survives WinRM session exit)
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
$startScript = Join-Path $Root "deploy\windows\GS_START_FULL_STACK.ps1"
if (-not (Test-Path $startScript)) { throw "Missing $startScript" }

$taskName = "GoldenShieldStackStart"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument (
    "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`" -Root `"$Root`""
)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger (New-ScheduledTaskTrigger -AtLogon) -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "STACK_TASK_STARTED"
$regDaemon = Join-Path $Root "deploy\windows\REGISTER_GS_DAEMON_TASK.ps1"
if (Test-Path $regDaemon) {
    try {
        & $regDaemon -Root $Root
    } catch {
        Write-Warning "DAEMON_TASK_FAIL $($_.Exception.Message)"
    }
}
