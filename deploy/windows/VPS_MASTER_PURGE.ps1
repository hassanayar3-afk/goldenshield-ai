# GoldenShield 2.0 — conflict purge + port 8790 freedom (sovereign root only)
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
$sovereign = (Resolve-Path $Root -ErrorAction SilentlyContinue).Path
if (-not $sovereign) {
    Write-Error "Sovereign root missing: $Root"
    exit 1
}

Write-Host "=== VPS_MASTER_PURGE root=$sovereign ==="

# 1) Legacy workspace folders (keep only GoldenShield_Binance)
$legacyRoots = @(
    "C:\GoldenShield",
    "C:\GoldenShield_Old",
    "C:\GoldenShield_Backup",
    "C:\GoldenShield-Binance",
    "C:\gs_binance"
)
$purged = @()
foreach ($dir in $legacyRoots) {
    if (-not (Test-Path $dir)) { continue }
    $resolved = (Resolve-Path $dir).Path
    if ($resolved -eq $sovereign) { continue }
    try {
        Remove-Item $resolved -Recurse -Force -ErrorAction Stop
        $purged += $resolved
    } catch {
        Write-Warning "Could not remove $resolved : $($_.Exception.Message)"
    }
}

# Quick-tunnel junk outside runtime
Get-ChildItem "C:\Users" -Recurse -Filter "trycloudflare*.txt" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "*GoldenShield_Binance*" } |
    ForEach-Object { Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue }

# 2) Kill python/pm2 listeners outside sovereign root (8790 conflicts)
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and (
        ($_.CommandLine -match "python" -and $_.CommandLine -notmatch [regex]::Escape($sovereign)) -or
        ($_.CommandLine -match "terminal_app\.server|fast_router|neural_matrix|main\.py|cloudflared")
    )
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

try {
    if (Get-Command pm2 -ErrorAction SilentlyContinue) {
        pm2 kill 2>$null | Out-Null
    }
} catch { }

Start-Sleep -Seconds 2

# Kill sovereign duplicates (clean slate before PM2)
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match [regex]::Escape($sovereign) -and
    $_.CommandLine -match "terminal_app\.server|fast_router|neural_matrix|main\.py|deploy_ops\\tunnel\.py"
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2

# 3) Port 8790 freedom
$port8790 = Get-NetTCPConnection -LocalPort 8790 -State Listen -ErrorAction SilentlyContinue
if ($port8790) {
    foreach ($c in $port8790) {
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
}
$still = @(Get-NetTCPConnection -LocalPort 8790 -State Listen -ErrorAction SilentlyContinue).Count
Write-Host "PORT_8790_LISTENERS=$still"
Write-Host "PURGED_DIRS=$($purged -join ';')"
Write-Host "PURGE_OK"
