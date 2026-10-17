param(
    [Parameter(Mandatory = $true)][string]$WebhookUrl,
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Stop"
$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
    New-Item -ItemType File -Path $envFile -Force | Out-Null
}
$lines = @(Get-Content $envFile -ErrorAction SilentlyContinue)
$map = @{
    "DISCORD_NOTIFY_ENABLED" = "true"
    "DISCORD_WEBHOOK_URL"    = $WebhookUrl.Trim()
}
$out = New-Object System.Collections.Generic.List[string]
$seen = @{}
foreach ($line in $lines) {
    if ($line -match "^([A-Za-z_][A-Za-z0-9_]*)=(.*)$") {
        $k = $Matches[1]
        if ($map.ContainsKey($k)) {
            $out.Add("$k=$($map[$k])")
            $seen[$k] = $true
            continue
        }
    }
    $out.Add($line)
}
foreach ($k in $map.Keys) {
    if (-not $seen[$k]) { $out.Add("$k=$($map[$k])") }
}
$out | Set-Content $envFile -Encoding UTF8
Write-Host "DISCORD_ENV_OK"
