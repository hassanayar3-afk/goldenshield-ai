import os
from dotenv import load_dotenv
import winrm

load_dotenv()
s = winrm.Session(
    f"http://{os.getenv('WIN_HOST')}:5985/wsman",
    auth=(os.getenv("WIN_USER"), os.getenv("WIN_PASSWORD")),
    transport="basic",
    server_cert_validation="ignore",
)
ps = """
$n = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main.py' }).Count
Write-Output "BOT_PROCS=$n"
Write-Output ("ENV=" + (Test-Path 'C:\\GoldenShield_Binance\\.env'))
Write-Output ("MAIN=" + (Test-Path 'C:\\GoldenShield_Binance\\main.py'))
$e = 'C:\\GoldenShield_Binance\\storage\\logs\\bot_stderr.log'
if (Test-Path $e) { Get-Content $e -Tail 10 }
schtasks /Query /TN GoldenShieldBotOfficial /FO LIST 2>&1 | Select-Object -First 4
$py = 'C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\python.exe'
Set-Location 'C:\\GoldenShield_Binance'
$env:PYTHONPATH = 'C:\\GoldenShield_Binance'
& $py -c "import main" 2>&1 | Select-Object -First 20
$d = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'gs_daemon' }).Count
Write-Output "DAEMON=$d"
"""
r = s.run_ps(ps)
print(r.std_out.decode("utf-8", "replace"))
