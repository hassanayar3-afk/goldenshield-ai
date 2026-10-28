# GoldenShield — منع السكون إجباري (24/7) على Windows Server / VPS
# يُستدعى من START_BOT_24_7.bat أو كمهمة مجدولة

param(
    [switch]$Loop,
    [switch]$RegisterTask
)

$ErrorActionPreference = "Continue"

function Set-NoSleepPowerCfg {
    powercfg -change -standby-timeout-ac 0 | Out-Null
    powercfg -change -standby-timeout-dc 0 | Out-Null
    powercfg -change -hibernate-timeout-ac 0 | Out-Null
    powercfg -change -hibernate-timeout-dc 0 | Out-Null
    powercfg -change -monitor-timeout-ac 0 | Out-Null
    powercfg -change -monitor-timeout-dc 0 | Out-Null
    powercfg -hibernate off | Out-Null
    Write-Host "POWERCFG_NO_SLEEP_OK"
}

function Register-NoSleepTask {
    $taskName = "GoldenShieldNoSleepGuard"
    $self = $MyInvocation.MyCommand.Path
    if (-not $self) { $self = Join-Path $PSScriptRoot "ENFORCE_NO_SLEEP.ps1" }
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$self`" -Loop"
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Write-Host "TASK_REGISTERED $taskName"
}

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class NoSleep {
  [DllImport("kernel32.dll")]
  public static extern uint SetThreadExecutionState(uint esFlags);
  public const uint ES_CONTINUOUS = 0x80000000;
  public const uint ES_SYSTEM_REQUIRED = 0x00000001;
  public const uint ES_DISPLAY_REQUIRED = 0x00000002;
}
"@

Set-NoSleepPowerCfg

if ($RegisterTask) {
    Register-NoSleepTask
    exit 0
}

if ($Loop) {
    while ($true) {
        [void][NoSleep]::SetThreadExecutionState(
            [NoSleep]::ES_CONTINUOUS -bor [NoSleep]::ES_SYSTEM_REQUIRED -bor [NoSleep]::ES_DISPLAY_REQUIRED
        )
        Start-Sleep -Seconds 45
    }
}

[void][NoSleep]::SetThreadExecutionState(
    [NoSleep]::ES_CONTINUOUS -bor [NoSleep]::ES_SYSTEM_REQUIRED -bor [NoSleep]::ES_DISPLAY_REQUIRED
)
Write-Host "NO_SLEEP_PULSE_OK"
