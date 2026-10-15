# Register GoldenShield auto-start at boot + logon (run_golden_shield.bat)
param(
    [string]$Root = "C:\GoldenShield_Binance",
    [switch]$SkipRegister
)
$ErrorActionPreference = "Continue"
$bat = Join-Path $Root "deploy_ops\run_golden_shield.bat"
if (-not (Test-Path $bat)) {
    Write-Warning "Missing $bat"
    exit 2
}
if ($SkipRegister) {
    Write-Output "BOOT_REGISTER_SKIP"
    exit 0
}
$taskName = "GoldenShieldAutoStart"
$action = New-ScheduledTaskAction -Execute $bat -WorkingDirectory $Root
$triggers = @(
    (New-ScheduledTaskTrigger -AtStartup),
    (New-ScheduledTaskTrigger -AtLogon)
)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 2) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Force | Out-Null
Write-Output "BOOT_TASK_OK $taskName"
