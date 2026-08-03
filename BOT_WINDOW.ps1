# نافذة حالة مستقرة — بدون رموز/إيموجي، وبدون تجميد QuickEdit
# إغلاق هذه النافذة لا يوقف البوت

$ErrorActionPreference = "Continue"
$Root = "C:\GoldenShield_Binance"
$Log = Join-Path $Root "storage\logs\bot_stdout.log"

try {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class ConsoleQuickEdit {
  const int STD_INPUT_HANDLE = -10;
  const uint ENABLE_QUICK_EDIT = 0x0040;
  const uint ENABLE_EXTENDED = 0x0080;
  [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr GetStdHandle(int n);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool GetConsoleMode(IntPtr h, out uint mode);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool SetConsoleMode(IntPtr h, uint mode);
  public static void Disable() {
    IntPtr h = GetStdHandle(STD_INPUT_HANDLE);
    uint mode;
    if (!GetConsoleMode(h, out mode)) return;
    mode &= ~ENABLE_QUICK_EDIT;
    mode |= ENABLE_EXTENDED;
    SetConsoleMode(h, mode);
  }
}
"@ -ErrorAction Stop
    [ConsoleQuickEdit]::Disable()
} catch {}

try {
    $Host.UI.RawUI.WindowTitle = "GoldenShield BOT STATUS"
    $Host.UI.RawUI.BufferSize = New-Object System.Management.Automation.Host.Size(120, 40)
} catch {}

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

function Get-MainInfo {
    $list = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match '^(python|pythonw|py)\.exe$' -and
        $_.CommandLine -and
        $_.CommandLine -match 'main\.py'
    })
    return $list
}

function Get-CleanLogLines([int]$n = 10) {
    if (-not (Test-Path $Log)) { return @("(no log yet)") }
    try {
        $raw = Get-Content -Path $Log -Tail 40 -ErrorAction SilentlyContinue
    } catch {
        return @("(log read error)")
    }
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($line in $raw) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        # أبقي الحروف/الأرقام والرموز الأساسية فقط — يمنع التداخل والتشويه
        $clean = [regex]::Replace($line, '[^\x20-\x7E]', '')
        $clean = $clean.Trim()
        if ($clean.Length -lt 3) { continue }
        # اختصر الأسطر الطويلة
        if ($clean.Length -gt 100) { $clean = $clean.Substring(0, 100) }
        $out.Add($clean)
    }
    if ($out.Count -eq 0) { return @("(log has no readable ASCII lines)") }
    $start = [Math]::Max(0, $out.Count - $n)
    return @($out.GetRange($start, $out.Count - $start))
}

while ($true) {
    try { [ConsoleQuickEdit]::Disable() } catch {}
    Clear-Host
    $mains = Get-MainInfo
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    Write-Host ""
    Write-Host "========================================================"
    Write-Host "  GoldenShield AI  |  BOT STATUS WINDOW"
    Write-Host "========================================================"
    Write-Host ""

    if ($mains.Count -ge 1) {
        Write-Host "  STATUS   : ACTIVE  (bot is running)" -ForegroundColor Green
        Write-Host ("  INSTANCES: " + $mains.Count)
        Write-Host ("  PID      : " + (($mains | ForEach-Object { $_.ProcessId }) -join ", "))
    } else {
        Write-Host "  STATUS   : STOPPED  (bot is NOT running)" -ForegroundColor Red
        Write-Host "  ACTION   : use desktop shortcut  START BOT"
    }

    Write-Host ("  FOLDER   : " + $Root)
    Write-Host ("  TIME     : " + $now)
    Write-Host ""
    Write-Host "  ---- last readable log lines ----" -ForegroundColor Cyan
    foreach ($ln in (Get-CleanLogLines 12)) {
        Write-Host ("  " + $ln)
    }
    Write-Host ""
    Write-Host "--------------------------------------------------------"
    Write-Host "  Auto-refresh every 5 sec"
    Write-Host "  Closing this window does NOT stop the bot"
    Write-Host "  To stop bot fully: use STOP BOT"
    Write-Host "  Tip: do NOT click inside this window (prevents freeze)"
    Write-Host "--------------------------------------------------------"

    Start-Sleep -Seconds 5
}
