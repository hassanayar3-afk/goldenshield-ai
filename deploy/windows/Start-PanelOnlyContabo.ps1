# Contabo: Mobile API + نفق فقط — البوت على اللابتوب + GS_PANEL_REMOTE_SNAPSHOT_ONLY
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
Set-Location $Root
. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")

$envFile = Join-Path $Root ".env"
$c = Get-Content $envFile -Raw -Encoding UTF8
foreach ($pair in @(
    @{ K = "GS_PANEL_REMOTE_SNAPSHOT_ONLY"; V = "true" },
    @{ K = "BOT_FORCE_ACTIVE"; V = "false" }
)) {
    $k = $pair.K
    $v = $pair.V
    if ($c -match "(?m)^$k=") {
        $c = [regex]::Replace($c, "(?m)^$k=.*", "${k}=${v}", 1)
    } else {
        $c = $c.TrimEnd() + "`n${k}=${v}`n"
    }
}
Set-Content $envFile $c -Encoding UTF8

Stop-ScheduledTask -TaskName GoldenShieldDaemon -ErrorAction SilentlyContinue
$kill = Join-Path $Root "scripts\gs_kill_all.ps1"
if (Test-Path $kill) { & $kill }
Start-Sleep -Seconds 2

$py = & (Join-Path $PSScriptRoot "Resolve-GsPython.ps1") -Root $Root
Start-Process -FilePath $py -ArgumentList @("-m", "terminal_app.server") -WorkingDirectory $Root -WindowStyle Hidden
Start-Sleep -Seconds 4
& (Join-Path $PSScriptRoot "START_CLOUDFLARE_TUNNEL.ps1") -Root $Root
Write-Host "PANEL_ONLY_OK — snapshot from laptop sync; open tunnel URL + pair_code"
