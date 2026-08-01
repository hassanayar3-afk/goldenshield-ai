Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
' Force classic CMD window (not PowerShell / Windows Terminal flash-close)
cmd = "cmd.exe /k cd /d """ & folder & """ && title GoldenShield Binance Demo && call 00_START.bat"
sh.Run cmd, 1, False
