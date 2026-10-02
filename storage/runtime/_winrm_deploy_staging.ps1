
$ErrorActionPreference='Continue'
$bot='C:\GoldenShield_Binance'
$arch=Join-Path $bot 'storage\runtime\_archived_launchers'
New-Item -ItemType Directory -Force -Path $arch | Out-Null
$move=@(
  '00_START_KEEP_OPEN.bat','00_START_VISIBLE.vbs','00_LIVE_CONSOLE.bat',
  'run_official_bot.bat','run_official_bot.ps1'
)
foreach($n in $move){
  $p=Join-Path $bot $n
  if(Test-Path $p){
    Move-Item $p (Join-Path $arch $n) -Force
    Write-Host ("ARCHIVED "+$n)
  }
}
# Patch .env no-sleep / binance / force active
$envp=Join-Path $bot '.env'
if(Test-Path $envp){
  $map=@{
    'NO_SLEEP_MODE'='true'
    'LOOP_INTERVAL_SECONDS'='4'
    'TELEGRAM_LIVE_SIGNALS'='true'
    'TELEGRAM_LIVE_SIGNALS_SECONDS'='4'
    'TELEGRAM_LIVE_POSITIONS_SECONDS'='3'
    'BOT_FORCE_ACTIVE'='true'
    'EXECUTION_BACKEND'='binance'
    'SSOT_SYNC_ENABLED'='true'
    'ENTERPRISE_PIPELINE_ENABLED'='true'
    'BINANCE_DEMO_TRADING'='true'
  }
  $lines=Get-Content $envp -Encoding UTF8
  $seen=@{}
  $out=@()
  foreach($line in $lines){
    if($line -match '^\s*#' -or $line -notmatch '='){ $out += $line; continue }
    $k=($line -split '=',2)[0].Trim()
    if($map.ContainsKey($k)){ $out += "$k=$($map[$k])"; $seen[$k]=1 }
    elseif($k -match '^(MT5_|BOT_AUTO_SYNC_MT5)'){ continue }
    else { $out += $line }
  }
  foreach($k in $map.Keys){ if(-not $seen.ContainsKey($k)){ $out += "$k=$($map[$k])" } }
  $utf8=New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllLines($envp, $out, $utf8)
  Write-Host 'ENV_NO_SLEEP_OK'
}
# Kill old + start new visible package
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $bot 'scripts\gs_kill_all.ps1')
Start-Sleep -Seconds 2
# Ensure hidden worker files are gone
foreach($n in @('run_official_bot.ps1','run_official_bot.bat','00_START_KEEP_OPEN.bat','00_LIVE_CONSOLE.bat')){
  $p=Join-Path $bot $n
  if(Test-Path $p){
    $arch=Join-Path $bot 'storage\runtime\_archived_launchers'
    New-Item -ItemType Directory -Force -Path $arch | Out-Null
    Move-Item $p (Join-Path $arch $n) -Force
    Write-Host ("ARCHIVED "+$n)
  }
}
schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
$flag=Join-Path $bot 'storage\runtime\user_stopped.flag'
if(Test-Path $flag){ Remove-Item $flag -Force }
$lock=Join-Path $bot 'storage\runtime\bot_instance.lock'
if(Test-Path $lock){ Remove-Item $lock -Force }
if(Test-Path 'C:\ProgramData\GoldenShield\bot_instance.lock'){ Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue }
powercfg -change -standby-timeout-ac 0 | Out-Null
powercfg -change -hibernate-timeout-ac 0 | Out-Null

# Start daemon OUTSIDE SSH job via Scheduled Task (survives SSH disconnect)
try {
  $actionDaemon = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$bot\gs_daemon.ps1`"" -WorkingDirectory $bot
  $prin = New-ScheduledTaskPrincipal -UserId 'Administrator' -LogonType S4U -RunLevel Highest
  $setOn = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 365)
  Unregister-ScheduledTask -TaskName 'GoldenShieldBotOfficial' -Confirm:$false -EA SilentlyContinue
  Register-ScheduledTask -TaskName 'GoldenShieldBotOfficial' -Action $actionDaemon -Principal $prin -Settings $setOn -Trigger (New-ScheduledTaskTrigger -AtStartup) -Force | Out-Null
  Start-ScheduledTask -TaskName 'GoldenShieldBotOfficial' | Out-Null
  Write-Host 'TASK_DAEMON_STARTED'
} catch {
  Write-Host ('TASK_DAEMON_WARN ' + $_.Exception.Message)
  # Fallback breakaway Start-Process
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = 'powershell.exe'
  $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$bot\gs_daemon.ps1`""
  $psi.WorkingDirectory = $bot
  $psi.UseShellExecute = $true
  $psi.WindowStyle = 'Hidden'
  [System.Diagnostics.Process]::Start($psi) | Out-Null
  Write-Host 'FALLBACK_PROCESS_START'
}
Start-Sleep -Seconds 15

# Pulse board for RDP session if available
try {
  $actionPulse = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoExit -NoProfile -ExecutionPolicy Bypass -File `"$bot\live_console.ps1`"" -WorkingDirectory $bot
  $principal = New-ScheduledTaskPrincipal -UserId 'Administrator' -LogonType Interactive -RunLevel Highest
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
  Unregister-ScheduledTask -TaskName 'GS_VisiblePulse' -Confirm:$false -EA SilentlyContinue
  Unregister-ScheduledTask -TaskName 'GS_VisibleBot' -Confirm:$false -EA SilentlyContinue
  Register-ScheduledTask -TaskName 'GS_VisiblePulse' -Action $actionPulse -Principal $principal -Settings $settings -Force | Out-Null
  Start-ScheduledTask -TaskName 'GS_VisiblePulse' -EA SilentlyContinue
} catch {
  Write-Host ('VISIBLE_TASK_WARN ' + $_.Exception.Message)
}

$procs=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' })
Write-Host ('BOT_PROCS=' + $procs.Count)
foreach($p in $procs){ Write-Host ('PID=' + $p.ProcessId) }
$daemonN=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'gs_daemon\.ps1' })
Write-Host ('DAEMON=' + $daemonN.Count)
Write-Host ('HIDDEN_WORKER=' + (Test-Path (Join-Path $bot 'run_official_bot.ps1')))
Write-Host ('START_BAT=' + (Test-Path (Join-Path $bot 'start_bot.bat')))
Write-Host ('RESTART_BAT=' + (Test-Path (Join-Path $bot 'restart_bot.bat')))
Write-Host ('STOP_BAT=' + (Test-Path (Join-Path $bot 'stop_bot.bat')))
Write-Host ('CORE_CMD=' + (Test-Path (Join-Path $bot 'run_bot_visible.cmd')))
Write-Host ('PULSE_PS1=' + (Test-Path (Join-Path $bot 'live_console.ps1')))
Write-Host ('DAEMON_PS1=' + (Test-Path (Join-Path $bot 'gs_daemon.ps1')))
if(Test-Path (Join-Path $bot 'storage\logs\gs_daemon.log')){
  Write-Host '--- DAEMON LOG ---'
  Get-Content (Join-Path $bot 'storage\logs\gs_daemon.log') -Tail 15 -EA SilentlyContinue
}
if(Test-Path (Join-Path $bot 'storage\logs\bot_stderr.log')){
  Write-Host '--- STDERR TAIL ---'
  Get-Content (Join-Path $bot 'storage\logs\bot_stderr.log') -Tail 20 -EA SilentlyContinue
}
Write-Host 'PACKAGE_DEPLOY_OK'
