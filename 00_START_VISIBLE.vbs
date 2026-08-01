Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = folder
' نافذة CMD مرئية وتبقى مفتوحة
sh.Run "cmd.exe /k cd /d """ & folder & """ && call 00_START.bat", 1, False
