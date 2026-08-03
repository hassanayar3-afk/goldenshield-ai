# عامل الخلفية الرسمي — مثيل واحد، بلا نافذة ظاهرة
# المهمة: GoldenShieldBotOfficial — لا تشغّل يدوياً (استخدم START_BOT.bat)

$ErrorActionPreference = "Continue"
$Root = "C:\GoldenShield_Binance"
Set-Location $Root

$env:PYTHONPATH = $Root
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root
$env:GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT = "true"
$env:GOLDENSHIELD_LOCK_FAIL_CLOSED = "true"
$env:DB_PATH = Join-Path $Root "storage\db\goldenshield.db"
$env:BOT_FORCE_ACTIVE = "true"

$logDir = Join-Path $Root "storage\logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}
$log = Join-Path $logDir "bot_stdout.log"
$runtime = Join-Path $Root "storage\runtime"
if (-not (Test-Path $runtime)) {
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
}
$stopFlag = Join-Path $runtime "user_stopped.flag"
if (Test-Path $stopFlag) {
    Remove-Item $stopFlag -Force -ErrorAction SilentlyContinue
}

$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
if (-not (Test-Path $py)) { $py = "py" }

function Get-MainPids {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match '^(python|pythonw|py)\.exe$' -and
            $_.CommandLine -and
            $_.CommandLine -match 'main\.py'
        } |
        Select-Object -ExpandProperty ProcessId)
}

function Write-WorkerLog([string]$msg) {
    Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg) -ErrorAction SilentlyContinue
}

$myPid = $PID
$mains = Get-MainPids
if ($mains.Count -ge 1) {
    Write-WorkerLog ("WORKER_SKIP already_running mains=" + ($mains -join ","))
    exit 0
}

# أوقف عمال bat/ps1 المكررين غير هذا العملية
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessId -ne $myPid -and
    $_.CommandLine -and
    $_.CommandLine -match 'run_official_bot\.(bat|ps1)'
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-WorkerLog "WORKER_START hidden single"

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
        $arg = "/c `"`"$py`" -u main.py >> `"$log`" 2>&1`""
        $p = Start-Process -FilePath "cmd.exe" -ArgumentList $arg -WorkingDirectory $Root `
            -WindowStyle Hidden -PassThru
        if ($null -ne $p) {
            Wait-Process -Id $p.Id -ErrorAction SilentlyContinue
        }
        Write-WorkerLog "WORKER_EXIT restart"
    }

    Start-Sleep -Seconds 5
}
