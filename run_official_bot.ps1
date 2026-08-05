# GoldenShield Official Master Worker — v2026.08 ENTERPRISE FULL
# المهمة: GoldenShieldBotOfficial
# لا تشغّل يدوياً — استخدم START_BOT.bat / REST_BOT.bat / STOP_BOT.bat فقط
# يضم: project_rules · Hybrid 70/90 · SSoT · Pipeline Fail-Closed · Post-Mortem · CB · Micro TF

$ErrorActionPreference = "Continue"
$Root = "C:\GoldenShield_Binance"
$WorkerTag = "GS_OFFICIAL_WORKER_v2026_08_ENTERPRISE_FULL"
Set-Location $Root

# —— بيئة رسمية (لا تكتب أسراراً؛ تُقرأ من .env عبر Python) ——
$env:PYTHONPATH = $Root
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root
$env:GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT = "true"
$env:GOLDENSHIELD_LOCK_FAIL_CLOSED = "true"
$env:DB_PATH = Join-Path $Root "storage\db\goldenshield.db"
$env:BOT_FORCE_ACTIVE = "true"

# قواعد المؤسسة + الهجين + إغلاق الفجوات (دائم)
if (-not $env:HYBRID_SIGNAL_MODE) { $env:HYBRID_SIGNAL_MODE = "true" }
if (-not $env:PROJECT_REFERENCE_CAPITAL) { $env:PROJECT_REFERENCE_CAPITAL = "5000" }
if (-not $env:PROJECT_MIN_TRADE_NOTIONAL) { $env:PROJECT_MIN_TRADE_NOTIONAL = "25" }
if (-not $env:PROJECT_MIN_EXCHANGE_NOTIONAL) { $env:PROJECT_MIN_EXCHANGE_NOTIONAL = "5" }
if (-not $env:AUTO_ENTRY_MIN_PERCENT) { $env:AUTO_ENTRY_MIN_PERCENT = "90" }
if (-not $env:TELEGRAM_SIGNAL_MIN_PERCENT) { $env:TELEGRAM_SIGNAL_MIN_PERCENT = "70" }
if (-not $env:MANUAL_ENTRY_REQUIRED) { $env:MANUAL_ENTRY_REQUIRED = "false" }
if (-not $env:TELEGRAM_LIVE_SIGNALS) { $env:TELEGRAM_LIVE_SIGNALS = "true" }
if (-not $env:TELEGRAM_LIVE_SIGNALS_SECONDS) { $env:TELEGRAM_LIVE_SIGNALS_SECONDS = "15" }
if (-not $env:TELEGRAM_LIVE_POSITIONS_SECONDS) { $env:TELEGRAM_LIVE_POSITIONS_SECONDS = "1" }
if (-not $env:ENTERPRISE_PIPELINE_ENABLED) { $env:ENTERPRISE_PIPELINE_ENABLED = "true" }
if (-not $env:SSOT_SYNC_ENABLED) { $env:SSOT_SYNC_ENABLED = "true" }
if (-not $env:POST_MORTEM_ENGINE_ACTIVE) { $env:POST_MORTEM_ENGINE_ACTIVE = "true" }
if (-not $env:CIRCUIT_BREAKER_MAX_LOSSES) { $env:CIRCUIT_BREAKER_MAX_LOSSES = "3" }

$logDir = Join-Path $Root "storage\logs"
$runtime = Join-Path $Root "storage\runtime"
$reports = Join-Path $Root "storage\reports"
$dbDir = Join-Path $Root "storage\db"
foreach ($d in @($logDir, $runtime, $dbDir, $reports, (Join-Path $reports "post_mortem"))) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
    }
}
$log = Join-Path $logDir "bot_stdout.log"
$stopFlag = Join-Path $runtime "user_stopped.flag"
$lockFile = Join-Path $runtime "bot_instance.lock"
$pdLock = "C:\ProgramData\GoldenShield\bot_instance.lock"

function Write-WorkerLog([string]$msg) {
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $WorkerTag, $msg
    Add-Content -Path $log -Value $line -ErrorAction SilentlyContinue
}

function Get-MainPids {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match '^(python|pythonw|py)\.exe$' -and
            $_.CommandLine -and
            $_.CommandLine -match 'main\.py'
        } |
        Select-Object -ExpandProperty ProcessId)
}

function Clear-OperationalLocks {
    foreach ($p in @($stopFlag, $lockFile, $pdLock)) {
        if (Test-Path $p) {
            Remove-Item $p -Force -ErrorAction SilentlyContinue
        }
    }
    Get-ChildItem -Path $runtime -Filter "*.tmp" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $runtime -Filter "*.temp" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
}

$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
if (-not (Test-Path $py)) { $py = "py" }

function Invoke-EnterprisePreflight {
    $pre = Join-Path $Root "storage\runtime\_worker_preflight.py"
    @"
import os, sys
sys.path.insert(0, r"C:\GoldenShield_Binance")
os.chdir(r"C:\GoldenShield_Binance")
from config.project_rules import (
    load_project_rules, assert_entry_notional,
    is_hybrid_auto_score, is_hybrid_manual_broadcast_score,
    HYBRID_AUTO_MIN_PERCENT, HYBRID_MANUAL_MIN_PERCENT,
    ENTERPRISE_MANUAL_PREFERRED_PERCENT, ENTERPRISE_TIMEFRAMES,
)
from core.constants import ANALYSIS_TIMEFRAMES, SIGNAL_NOTIFY_MIN_PERCENT, SIGNAL_AUTO_PERCENT
from operations.startup_cleanup import run_startup_cleanup
from core.pre_flight import run_pre_flight_checks
from core.enterprise_pipeline import PIPELINE_STAGES
from operations.post_mortem import record_close_post_mortem
r = load_project_rules()
assert float(r.reference_capital) >= 5000
assert float(r.min_trade_notional) >= 25
assert r.hybrid_mode and r.enterprise_pipeline
assert HYBRID_AUTO_MIN_PERCENT == 90 and SIGNAL_AUTO_PERCENT == 90
assert HYBRID_MANUAL_MIN_PERCENT == 70 and SIGNAL_NOTIFY_MIN_PERCENT == 70
assert ENTERPRISE_MANUAL_PREFERRED_PERCENT == 70
assert set(ANALYSIS_TIMEFRAMES) >= set(["4h","1h","15m","5m","1m"])
assert set(ENTERPRISE_TIMEFRAMES) >= set(["4h","1h","15m","5m","1m"])
assert len(PIPELINE_STAGES) >= 8
assert is_hybrid_auto_score(9) and is_hybrid_auto_score(10)
assert is_hybrid_manual_broadcast_score(7) and is_hybrid_manual_broadcast_score(8)
assert not is_hybrid_auto_score(8)
assert assert_entry_notional(0.001, 10)
assert callable(record_close_post_mortem)
main_src = open("main.py", encoding="utf-8", errors="replace").read()
assert "FAIL-CLOSED" in main_src or "FAIL_CLOSED" in main_src
tex = open("execution/trade_executor.py", encoding="utf-8", errors="replace").read()
assert "_record_post_mortem_safe" in tex
run_startup_cleanup()
run_pre_flight_checks(soft=True)
print(
    "PREFLIGHT_OK", "ENTERPRISE_FULL",
    "auto", HYBRID_AUTO_MIN_PERCENT, "manual", HYBRID_MANUAL_MIN_PERCENT,
    "cap", r.reference_capital, "min", r.min_trade_notional,
    "frames", ",".join(ANALYSIS_TIMEFRAMES),
    "BOT_FORCE", os.getenv("BOT_FORCE_ACTIVE", "true"),
)
"@ | Set-Content -Path $pre -Encoding UTF8
    try {
        $out = & $py $pre 2>&1
        Write-WorkerLog ("PREFLIGHT " + (($out | Out-String).Trim()))
    } catch {
        Write-WorkerLog ("PREFLIGHT_WARN " + $_.Exception.Message)
    }
}

if (-not (Test-Path (Join-Path $Root "main.py"))) {
    Write-WorkerLog "FATAL missing main.py"
    exit 1
}
if (-not (Test-Path (Join-Path $Root ".env"))) {
    Write-WorkerLog "FATAL missing .env"
    exit 1
}

$myPid = $PID
$mains = Get-MainPids
if ($mains.Count -ge 1) {
    Write-WorkerLog ("WORKER_SKIP already_running mains=" + ($mains -join ","))
    exit 0
}

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessId -ne $myPid -and
    $_.CommandLine -and
    $_.CommandLine -match 'run_official_bot\.(bat|ps1)'
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

Clear-OperationalLocks
Write-WorkerLog "WORKER_START hidden single root=$Root rules=5000/25/hybrid70-90/SSoT/pipeline/postmortem"
Invoke-EnterprisePreflight

while ($true) {
    if (Test-Path $stopFlag) {
        Write-WorkerLog "WORKER_STOP flag"
        exit 0
    }

    $mains = Get-MainPids
    if ($mains.Count -gt 1) {
        $keep = ($mains | Sort-Object)[0]
        foreach ($p in $mains) {
            if ($p -ne $keep) {
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Seconds 2
        continue
    }

    if ($mains.Count -eq 0) {
        Clear-OperationalLocks
        Write-WorkerLog "MAIN_LAUNCH"
        $arg = "/c `"`"$py`" -u main.py >> `"$log`" 2>&1`""
        $p = Start-Process -FilePath "cmd.exe" -ArgumentList $arg -WorkingDirectory $Root `
            -WindowStyle Hidden -PassThru
        if ($null -ne $p) {
            Wait-Process -Id $p.Id -ErrorAction SilentlyContinue
        }
        Write-WorkerLog "WORKER_EXIT restart_in_5s"
    }

    Start-Sleep -Seconds 5
}
