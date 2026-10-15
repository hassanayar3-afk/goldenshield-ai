# GoldenShield 2.0 — production reconciliation (purge + named tunnel + boot lock-in)
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
if (-not (Test-Path (Join-Path $Root "main.py"))) {
    Write-Error "main.py missing under $Root"
    exit 2
}
Set-Location $Root
$audit = Join-Path $Root "storage\runtime\gs_master_reconcile_audit.json"
$runtime = Join-Path $Root "storage\runtime"
New-Item -ItemType Directory -Force -Path $runtime | Out-Null

Write-Host "=== GS_MASTER_RECONCILE ==="

# --- Enforce .env: public URL + tunnel token from token file when needed ---
$envPath = Join-Path $Root ".env"
$raw = if (Test-Path $envPath) { Get-Content $envPath -Raw -Encoding UTF8 } else { "" }
$publicUrl = "https://violafashioniq.com/"
if ($raw -notmatch "(?m)^MOBILE_PUBLIC_BASE_URL=") {
    $raw = $raw.TrimEnd() + "`nMOBILE_PUBLIC_BASE_URL=$publicUrl`n"
} else {
    $raw = [regex]::Replace($raw, "(?m)^MOBILE_PUBLIC_BASE_URL=.*$", "MOBILE_PUBLIC_BASE_URL=$publicUrl", 1)
}
if ($raw -notmatch "(?m)^CLOUDFLARE_TUNNEL_ENABLED=") {
    $raw = $raw.TrimEnd() + "`nCLOUDFLARE_TUNNEL_ENABLED=true`n"
} else {
    $raw = [regex]::Replace($raw, "(?m)^CLOUDFLARE_TUNNEL_ENABLED=.*$", "CLOUDFLARE_TUNNEL_ENABLED=true", 1)
}
if ($raw -notmatch "(?m)^CLOUDFLARE_TUNNEL_LOCAL_URL=") {
    $raw = $raw.TrimEnd() + "`nCLOUDFLARE_TUNNEL_LOCAL_URL=http://127.0.0.1:8790`n"
}
$tokenFile = Join-Path $runtime "tunnel.token"
if ((Test-Path $tokenFile) -and ($raw -notmatch "(?m)^CLOUDFLARE_TUNNEL_TOKEN=.+")) {
    $tok = (Get-Content $tokenFile -Raw -Encoding ASCII).Trim()
    if ($tok.Length -gt 20) {
        if ($raw -match "(?m)^CLOUDFLARE_TUNNEL_TOKEN=") {
            $raw = [regex]::Replace($raw, "(?m)^CLOUDFLARE_TUNNEL_TOKEN=.*$", "CLOUDFLARE_TUNNEL_TOKEN=$tok", 1)
        } else {
            $raw = $raw.TrimEnd() + "`nCLOUDFLARE_TUNNEL_TOKEN=$tok`n"
        }
        Write-Host "TUNNEL_TOKEN_SYNCED_FROM_FILE"
    }
}
# Drop quick-tunnel hostname overrides in .env
$raw = [regex]::Replace($raw, "(?m)^MOBILE_PUBLIC_BASE_URL=.*trycloudflare\.com.*$", "MOBILE_PUBLIC_BASE_URL=$publicUrl", 1)
Set-Content -Path $envPath -Value $raw -Encoding UTF8

$purge = Join-Path $PSScriptRoot "VPS_MASTER_PURGE.ps1"
$cleanup = Join-Path $PSScriptRoot "Cleanup-GsLegacy.ps1"
$stable = Join-Path $PSScriptRoot "Ensure-GsStableMobileEnv.ps1"
$start = Join-Path $PSScriptRoot "GS_START_FULL_STACK.ps1"
if (Test-Path $purge) { & $purge -Root $Root }
if (Test-Path $cleanup) { & $cleanup -Root $Root -Aggressive }
if (Test-Path $stable) { & $stable -Root $Root }

& (Join-Path $PSScriptRoot "REGISTER_GS_BOOT_STACK.ps1") -Root $Root
& (Join-Path $PSScriptRoot "REGISTER_GS_DAEMON_TASK.ps1") -Root $Root
& (Join-Path $PSScriptRoot "REGISTER_GS_TUNNEL_TASK.ps1") -Root $Root
if (Test-Path $start) { & $start -Root $Root }

$py = & (Join-Path $PSScriptRoot "Resolve-GsPython.ps1") -Root $Root
$nm = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "neural_matrix\.py"
}).Count
if ($nm -lt 1) {
    Start-Process -FilePath $py -ArgumentList @(Join-Path $Root "core_engine\neural_matrix.py") `
        -WorkingDirectory $Root -WindowStyle Hidden
    Write-Host "NEURAL_MATRIX_STARTED"
}

Start-Sleep -Seconds 8
& $py (Join-Path $Root "deploy_ops\push_discord_live_status.py") 2>$null | Out-Null

function ProcCount([string]$pat) {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and $_.CommandLine -match $pat
    }).Count
}

$report = [ordered]@{
    ts = (Get-Date).ToUniversalTime().ToString("o")
    root = $Root
    processes = @{
        terminal_server = (ProcCount "terminal_app\.server")
        neural_matrix = (ProcCount "neural_matrix\.py")
        main_bot = (ProcCount "main\.py")
        gs_daemon = (ProcCount "gs_daemon")
        discord_bridge = (ProcCount "discord_bridge\.py")
        cloudflared = (ProcCount "cloudflared")
    }
    scheduled_tasks = @{}
    env = @{}
    health_local = $null
    health_public = $null
    live_balance = $null
}

foreach ($tn in @("GoldenShieldAutoStart", "GoldenShieldDaemon", "GoldenShieldTunnel")) {
    $t = Get-ScheduledTask -TaskName $tn -ErrorAction SilentlyContinue
    if ($t) {
        $info = Get-ScheduledTaskInfo -TaskName $tn
        $report.scheduled_tasks[$tn] = @{ state = $t.State.ToString(); last_result = $info.LastTaskResult }
    } else {
        $report.scheduled_tasks[$tn] = "MISSING"
    }
}

foreach ($k in @("CLOUDFLARE_TUNNEL_TOKEN", "MOBILE_PUBLIC_BASE_URL", "CLOUDFLARE_TUNNEL_LOCAL_URL", "DISCORD_WEBHOOK_URL", "BINANCE_DEMO_TRADING")) {
    if ($raw -match "(?m)^$([regex]::Escape($k))=(.*)$") {
        $v = $Matches[1].Trim()
        if ($k -match "TOKEN|SECRET|WEBHOOK|KEY|PASSWORD") {
            $report.env[$k] = if ($v) { "SET len=$($v.Length)" } else { "EMPTY" }
        } else {
            $report.env[$k] = $v
        }
    } else {
        $report.env[$k] = "MISSING"
    }
}

try {
    $h = Invoke-RestMethod "http://127.0.0.1:8790/api/health" -TimeoutSec 15
    $report.health_local = $h
} catch {
    $report.health_local = @{ ok = $false; error = $_.Exception.Message }
}

try {
    $pub = Invoke-WebRequest "https://violafashioniq.com/api/health" -UseBasicParsing -TimeoutSec 25
    $report.health_public = @{ status = $pub.StatusCode; body = $pub.Content.Substring(0, [Math]::Min(200, $pub.Content.Length)) }
} catch {
    $report.health_public = @{ ok = $false; error = $_.Exception.Message }
}

try {
    $pair = ""
    if ($raw -match "(?m)^MOBILE_PAIR_CODE=(.+)$") { $pair = $Matches[1].Trim().Trim('"').ToUpper() }
    if ($pair) {
        $pr = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8790/api/pair" -ContentType "application/json" `
            -Body (@{ pair_code = $pair; device_name = "ReconcileAudit" } | ConvertTo-Json) -TimeoutSec 20
        $hdr = @{ "X-GS-Token" = $pr.device_token }
        $st = Invoke-RestMethod "http://127.0.0.1:8790/api/status" -Headers $hdr -TimeoutSec 20
        $report.live_balance = @{
            equity = $st.status.balance
            free_cash = $st.status.free_cash
            exchange_ok = $st.status.exchange_ok
            bot_running = $st.status.bot_running
            balance_source = $st.status.balance_source
        }
    }
} catch {
    $report.live_balance = @{ error = $_.Exception.Message }
}

$report | ConvertTo-Json -Depth 6 | Set-Content -Path $audit -Encoding UTF8
Write-Host "AUDIT_JSON=$audit"
Write-Host "RECONCILE_DONE"
exit 0
