# GoldenShield LIVE CONSOLE — mirrors signals_board.txt every 1s (companion view)
# Closing this window does NOT stop the bot. Use stop_bot.bat to stop.

$ErrorActionPreference = "Continue"
$Root = "C:\GoldenShield_Binance"
$Board = Join-Path $Root "storage\runtime\signals_board.txt"
$Log = Join-Path $Root "storage\logs\bot_stdout.log"

try {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class ConsoleQuickEditGS {
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
    [ConsoleQuickEditGS]::Disable()
} catch {}

try { $Host.UI.RawUI.WindowTitle = "GoldenShield LIVE SIGNALS BOARD" } catch {}
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

function Get-MainInfo {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match '^(python|pythonw|py)\.exe$' -and
        $_.CommandLine -and
        $_.CommandLine -match 'main\.py'
    })
}

while ($true) {
    try { [ConsoleQuickEditGS]::Disable() } catch {}
    Clear-Host
    $mains = Get-MainInfo
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    Write-Host ""
    if ($mains.Count -eq 1) {
        Write-Host ("  BOT: ACTIVE (single)   PID: " + $mains[0].ProcessId) -ForegroundColor Green
    } elseif ($mains.Count -gt 1) {
        Write-Host ("  BOT: DUPLICATE WARNING  count=" + $mains.Count) -ForegroundColor Yellow
    } else {
        Write-Host "  BOT: STOPPED   use start_bot.bat" -ForegroundColor Red
    }
    Write-Host ("  TIME: " + $now + "   |   Pulse board refresh ~1s   |   Bot cycle ~4s")
    Write-Host "  PLATFORM: Binance only   |   No-Sleep: ON"
    Write-Host ""

    if (Test-Path $Board) {
        try {
            Get-Content -Path $Board -Encoding UTF8 -ErrorAction Stop | ForEach-Object { Write-Host $_ }
        } catch {
            Write-Host "  (cannot read signals_board.txt)"
        }
    } else {
        Write-Host "========================================================"
        Write-Host "  Waiting for signals board..."
        Write-Host "  (created after first analysis cycle)"
        Write-Host "========================================================"
        if (Test-Path $Log) {
            Write-Host "  ---- recent log tail ----"
            Get-Content $Log -Tail 15 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
        }
    }

    Write-Host ""
    Write-Host "  Tip: do not select text in this window (pauses scroll)"
    Write-Host "  Stop bot: stop_bot.bat   |   Restart: restart_bot.bat"
    Start-Sleep -Seconds 1
}
