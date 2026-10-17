# Contabo — تنظيف + بوت واحد + API + snapshot writer + نفق
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "=== STABILIZE AND RUN ===" -ForegroundColor Cyan

Stop-ScheduledTask -TaskName GoldenShieldDaemon -ErrorAction SilentlyContinue
Stop-ScheduledTask -TaskName GoldenShieldWatchdog -ErrorAction SilentlyContinue

$kill = Join-Path $Root "scripts\gs_kill_all.ps1"
if (Test-Path $kill) { & $kill }
Start-Sleep -Seconds 3

Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
    $_.CommandLine -and ($_.CommandLine -match 'gs_daemon\.ps1|main\.py|terminal_app\.server|gs_snapshot_writer')
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }

$runtime = Join-Path $Root "storage\runtime"
Remove-Item (Join-Path $runtime "bot_instance.lock") -Force -EA SilentlyContinue
Remove-Item "C:\ProgramData\GoldenShield\bot_instance.lock" -Force -EA SilentlyContinue
Remove-Item (Join-Path $runtime "user_stopped.flag") -Force -EA SilentlyContinue

$envFile = Join-Path $Root ".env"
$c = Get-Content $envFile -Raw -Encoding UTF8
foreach ($line in @(
    "GS_SKIP_RUNTIME_SYNC=true",
    "GS_PANEL_REMOTE_SNAPSHOT_ONLY=false",
    "BOT_FORCE_ACTIVE=true",
    "GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT=true",
    "GOLDENSHIELD_LOCK_FAIL_CLOSED=true"
)) {
    $k = ($line -split "=", 2)[0]
    if ($c -match ('(?m)^' + [regex]::Escape($k) + '=')) {
        $c = [regex]::Replace($c, ('(?m)^' + [regex]::Escape($k) + '=.*'), $line, 1)
    } else { $c = $c.TrimEnd() + "`n$line`n" }
}
Set-Content $envFile $c -Encoding UTF8

$py = & (Join-Path $scriptDir "Resolve-GsPython.ps1") -Root $Root
& $py scripts\test_binance_connection.py
if ($LASTEXITCODE -ne 0) { Write-Warning "Binance test failed — check keys/proxy"; exit 1 }

Start-Process powershell -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
    (Join-Path $Root "gs_daemon.ps1"), "-Root", $Root
) -WorkingDirectory $Root -WindowStyle Minimized

$snap = Join-Path $Root "deploy_ops\gs_snapshot_writer.py"
if (Test-Path $snap) {
    Start-Process -FilePath $py -ArgumentList @($snap) -WorkingDirectory $Root -WindowStyle Hidden
}

Start-Process -FilePath $py -ArgumentList @("-m", "terminal_app.server") -WorkingDirectory $Root -WindowStyle Hidden
Start-Sleep -Seconds 6
& (Join-Path $scriptDir "START_CLOUDFLARE_TUNNEL.ps1") -Root $Root
Start-Sleep -Seconds 8

try {
    $h = Invoke-RestMethod "http://127.0.0.1:8790/api/health" -TimeoutSec 30
    Write-Host ("health ok=" + $h.ok + " snap_age=" + $h.spinal.snapshot_age_sec + " fresh=" + $h.spinal.snapshot_fresh) -ForegroundColor Green
} catch { Write-Warning $_.Exception.Message }
try {
    $pl = Invoke-RestMethod "http://127.0.0.1:8790/api/mobile/pair-link" -TimeoutSec 30
    Write-Host ("PANEL " + $pl.panel_pair_url) -ForegroundColor Green
} catch { Write-Warning $_ }

Register-ScheduledTask -TaskName GoldenShieldWatchdog -Action (
    New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $scriptDir 'GS_WATCHDOG.ps1')`" -Root `"$Root`""
) -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)) -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries) -Force -ErrorAction SilentlyContinue | Out-Null

Write-Host "STABILIZE_DONE" -ForegroundColor Green
exit 0
