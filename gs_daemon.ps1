# Durable No-Sleep single-instance daemon for GoldenShield (Binance)
$ErrorActionPreference = "Continue"
$Root = "C:\GoldenShield_Binance"
Set-Location $Root

$env:PYTHONPATH = $Root
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root
$env:GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT = "true"
$env:GOLDENSHIELD_LOCK_FAIL_CLOSED = "true"
$env:BOT_FORCE_ACTIVE = "true"
$env:NO_SLEEP_MODE = "true"
$env:LOOP_INTERVAL_SECONDS = "4"
$env:TELEGRAM_LIVE_SIGNALS = "true"
$env:TELEGRAM_LIVE_SIGNALS_SECONDS = "4"
$env:TELEGRAM_LIVE_POSITIONS_SECONDS = "3"
$env:SSOT_SYNC_ENABLED = "true"
$env:ENTERPRISE_PIPELINE_ENABLED = "true"
$env:EXECUTION_BACKEND = "binance"

$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
if (-not (Test-Path $py)) { $py = "py" }
$logDir = Join-Path $Root "storage\logs"
$runtime = Join-Path $Root "storage\runtime"
New-Item -ItemType Directory -Force -Path $logDir, $runtime | Out-Null
$daemonLog = Join-Path $logDir "gs_daemon.log"
$stop = Join-Path $runtime "user_stopped.flag"

function Write-D([string]$m) {
    $line = "[{0}] [GS_VISIBLE_DAEMON] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m
    Add-Content -Path $daemonLog -Value $line -ErrorAction SilentlyContinue
}

Write-D "DAEMON_START"

while ($true) {
    if (Test-Path $stop) {
        Write-D "DAEMON_STOP flag"
        exit 0
    }

    $mains = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match '^(python|pythonw|py)\.exe$' -and $_.CommandLine -and $_.CommandLine -match 'main\.py'
    })
    if ($mains.Count -gt 1) {
        $keep = ($mains | Sort-Object ProcessId | Select-Object -First 1).ProcessId
        foreach ($m in $mains) {
            if ($m.ProcessId -ne $keep) {
                Stop-Process -Id $m.ProcessId -Force -ErrorAction SilentlyContinue
                Write-D ("KILLED_DUP=" + $m.ProcessId)
            }
        }
        Start-Sleep -Seconds 2
        continue
    }
    if ($mains.Count -eq 1) {
        Start-Sleep -Seconds 4
        continue
    }

    # Clear stale lock before launch so singleton can acquire
    Remove-Item (Join-Path $runtime "bot_instance.lock") -Force -ErrorAction SilentlyContinue
    Remove-Item "C:\ProgramData\GoldenShield\bot_instance.lock" -Force -ErrorAction SilentlyContinue

    Write-D "MAIN_LAUNCH"
    $outLog = Join-Path $logDir "bot_stdout.log"
    $errLog = Join-Path $logDir "bot_stderr.log"
    $p = Start-Process -FilePath $py -ArgumentList "-u", "main.py" -WorkingDirectory $Root `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru -WindowStyle Hidden
    if ($null -eq $p) {
        Write-D "MAIN_SPAWN_FAILED"
        Start-Sleep -Seconds 3
        continue
    }
    Write-D ("MAIN_PID=" + $p.Id)
    Wait-Process -Id $p.Id -ErrorAction SilentlyContinue
    Write-D ("MAIN_EXIT code=" + $p.ExitCode)
    Start-Sleep -Seconds 2
}
