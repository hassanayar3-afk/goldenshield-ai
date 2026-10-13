# Apply latest GoldenShield fixes on-box + restart full stack (run on VPS as Admin)
param(
    [string]$Root = "C:\GoldenShield_Binance",
    [string]$Branch = "cursor/win-remote-deploy-fix-2e26",
    [string]$DiscordWebhookUrl = ""
)
$ErrorActionPreference = "Continue"
Set-Location $Root

Write-Host "=== VPS_APPLY_FIX Root=$Root Branch=$Branch ==="

if ($DiscordWebhookUrl) {
    & (Join-Path $Root "deploy\windows\Set-GsDiscordEnv.ps1") -WebhookUrl $DiscordWebhookUrl -Root $Root
}

if (Test-Path (Join-Path $Root ".git")) {
    git fetch origin $Branch 2>&1
    git checkout $Branch 2>&1
    git pull origin $Branch 2>&1
} else {
    Write-Warning "No git repo — copy files manually or clone first"
}

$py = & (Join-Path $Root "deploy\windows\Resolve-GsPython.ps1") -Root $Root
Write-Host "PYTHON=$py"
& $py -m pip install -r requirements.txt --quiet
& $py scripts\bootstrap_storage.py

$discordOk = $false
if (Test-Path (Join-Path $Root ".env")) {
    $envLines = Get-Content (Join-Path $Root ".env")
    foreach ($k in @("DISCORD_WEBHOOK_URL", "DISCORD_BOT_TOKEN")) {
        if ($envLines -match "^$k=.+") { $discordOk = $true }
    }
}
if (-not $discordOk) {
    Write-Warning "Discord not configured in .env — set DISCORD_WEBHOOK_URL or BOT_TOKEN+CHANNEL_ID"
}

& (Join-Path $Root "deploy\windows\GS_START_FULL_STACK.ps1") -Root $Root
Start-Sleep -Seconds 8

try {
    $st = Invoke-RestMethod "http://127.0.0.1:8790/api/status" -Headers @{"X-GS-Token" = (Get-Content (Join-Path $Root "storage\runtime\mobile_devices.json") -Raw | ConvertFrom-Json).devices.PSObject.Properties.Name[0]} -TimeoutSec 30 -ErrorAction Stop
    Write-Host ("STATUS bot_running=" + $st.status.bot_running + " balance=" + $st.status.balance)
} catch {
    Write-Host "STATUS_CHECK skipped (pair token) - open http://127.0.0.1:8790/api/health"
}

Write-Host "=== VPS_APPLY_FIX_DONE ==="
