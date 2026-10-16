# Install / refresh Cloudflare Named Tunnel as Windows service (token from .env or param)
param(
    [string]$Root = "C:\GoldenShield_Binance",
    [string]$TunnelToken = ""
)
$ErrorActionPreference = "Continue"
Set-Location $Root
. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")

if (-not $TunnelToken) {
    $TunnelToken = "$(if ($env:CLOUDFLARE_TUNNEL_TOKEN) { $env:CLOUDFLARE_TUNNEL_TOKEN } else { '' })".Trim()
}
if (-not $TunnelToken) {
    $tf = Join-Path $Root "storage\runtime\tunnel.token"
    if (Test-Path $tf) {
        $TunnelToken = (Get-Content $tf -Raw -Encoding ASCII).Trim()
    }
}
if (-not $TunnelToken) {
    Write-Error "Missing tunnel token"
    exit 2
}

$runtime = Join-Path $Root "storage\runtime"
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
Set-Content -Path (Join-Path $runtime "tunnel.token") -Value $TunnelToken -Encoding ASCII -NoNewline

$envPath = Join-Path $Root ".env"
$raw = if (Test-Path $envPath) { Get-Content $envPath -Raw -Encoding UTF8 } else { "" }
foreach ($kv in @(
    "MOBILE_PUBLIC_BASE_URL=https://violafashioniq.com/",
    "CLOUDFLARE_TUNNEL_ENABLED=true",
    "CLOUDFLARE_TUNNEL_LOCAL_URL=http://127.0.0.1:8790"
)) {
    $k = ($kv -split "=", 2)[0]
    $v = ($kv -split "=", 2)[1]
    if ($raw -match "(?m)^$([regex]::Escape($k))=") {
        $raw = [regex]::Replace($raw, "(?m)^$([regex]::Escape($k))=.*$", "$k=$v", 1)
    } else {
        $raw = $raw.TrimEnd() + "`n$k=$v`n"
    }
}
if ($raw -match "(?m)^CLOUDFLARE_TUNNEL_TOKEN=") {
    $raw = [regex]::Replace($raw, "(?m)^CLOUDFLARE_TUNNEL_TOKEN=.*$", "CLOUDFLARE_TUNNEL_TOKEN=$TunnelToken", 1)
} else {
    $raw = $raw.TrimEnd() + "`nCLOUDFLARE_TUNNEL_TOKEN=$TunnelToken`n"
}
Set-Content -Path $envPath -Value $raw -Encoding UTF8

Stop-ScheduledTask -TaskName GoldenShieldTunnel -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "cloudflared|GS_TUNNEL_KEEPALIVE"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

$cf = Join-Path $Root "tools\cloudflared.exe"
if (-not (Test-Path $cf)) {
    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) { $cf = $cmd.Source }
}
if (-not (Test-Path $cf)) {
    Write-Error "cloudflared.exe not found"
    exit 3
}

Stop-Service -Name cloudflared -ErrorAction SilentlyContinue
& $cf service uninstall 2>$null | Out-Null
Start-Sleep -Seconds 2
& $cf service install $TunnelToken
$installCode = $LASTEXITCODE
Start-Service -Name cloudflared -ErrorAction SilentlyContinue
Start-Sleep -Seconds 6
$svc = Get-Service cloudflared -ErrorAction SilentlyContinue
Write-Host "SERVICE_INSTALL_EXIT=$installCode"
Write-Host "SERVICE_STATE=$($svc.Status)"

$py = & (Join-Path $PSScriptRoot "Resolve-GsPython.ps1") -Root $Root
if (-not @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "terminal_app\.server"
}).Count) {
    Start-Process $py -ArgumentList @("-m", "terminal_app.server") -WorkingDirectory $Root -WindowStyle Hidden
    Start-Sleep -Seconds 4
    Write-Host "TERMINAL_STARTED"
}

try {
    $h = Invoke-WebRequest "http://127.0.0.1:8790/api/health" -UseBasicParsing -TimeoutSec 15
    Write-Host "LOCAL_HEALTH=$($h.StatusCode)"
} catch {
    Write-Host "LOCAL_HEALTH_ERR=$($_.Exception.Message)"
}

try {
    $p = Invoke-WebRequest "https://violafashioniq.com/api/health" -UseBasicParsing -TimeoutSec 30
    Write-Host "PUBLIC_HEALTH=$($p.StatusCode)"
} catch {
    Write-Host "PUBLIC_HEALTH_ERR=$($_.Exception.Message)"
}

exit 0
