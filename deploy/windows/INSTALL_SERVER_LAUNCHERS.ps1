# ينسخ ملفات التشغيل إلى جذر C:\GoldenShield_Binance + اختصارات سطح المكتب
$ErrorActionPreference = "Stop"
$Target = "C:\GoldenShield_Binance"
$Here = $PSScriptRoot
$Root = Resolve-Path (Join-Path $Here "..\..")

$launchers = @(
    @{ Src = "deploy\windows\START_BOT_24_7.bat"; Dst = "START_BOT_24_7.bat" },
    @{ Src = "deploy\windows\STOP_BOT_FULL.bat"; Dst = "STOP_BOT_FULL.bat" },
    @{ Src = "deploy\windows\ENFORCE_NO_SLEEP.ps1"; Dst = "deploy\windows\ENFORCE_NO_SLEEP.ps1" },
    @{ Src = "gs_daemon.ps1"; Dst = "gs_daemon.ps1" },
    @{ Src = "GS_START_FULL_STACK.bat"; Dst = "GS_START_FULL_STACK.bat" },
    @{ Src = "deploy\windows\GS_START_FULL_STACK.ps1"; Dst = "deploy\windows\GS_START_FULL_STACK.ps1" },
    @{ Src = "deploy\windows\START_CLOUDFLARE_TUNNEL.ps1"; Dst = "deploy\windows\START_CLOUDFLARE_TUNNEL.ps1" },
    @{ Src = "deploy\windows\START_DISCORD_BRIDGE.ps1"; Dst = "deploy\windows\START_DISCORD_BRIDGE.ps1" },
    @{ Src = "deploy\windows\Import-GsDotEnv.ps1"; Dst = "deploy\windows\Import-GsDotEnv.ps1" }
)

foreach ($item in $launchers) {
    $from = Join-Path $Root $item.Src
    $to = Join-Path $Target $item.Dst
    $dir = Split-Path $to -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Copy-Item $from $to -Force
    Write-Host "COPIED $($item.Dst)"
}

# اختصارات سطح المكتب (Server)
$desktop = [Environment]::GetFolderPath("Desktop")
$wsh = New-Object -ComObject WScript.Shell
$startLink = Join-Path $desktop "GoldenShield START 24-7.lnk"
$stopLink = Join-Path $desktop "GoldenShield STOP.lnk"
$panelLink = Join-Path $desktop "GoldenShield Panel.lnk"

$s = $wsh.CreateShortcut($startLink)
$s.TargetPath = Join-Path $Target "START_BOT_24_7.bat"
$s.WorkingDirectory = $Target
$s.Save()

$t = $wsh.CreateShortcut($stopLink)
$t.TargetPath = Join-Path $Target "STOP_BOT_FULL.bat"
$t.WorkingDirectory = $Target
$t.Save()

$p = $wsh.CreateShortcut($panelLink)
$p.TargetPath = "http://127.0.0.1:8790/"
$p.Save()

Write-Host "DESKTOP_SHORTCUTS_OK $desktop"
