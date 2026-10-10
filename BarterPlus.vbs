Dim WshShell
Set WshShell = CreateObject("WScript.Shell")
' Ejecuta python sin consola (pythonw.exe) apuntando al archivo principal
WshShell.Run "pythonw.exe main.py", 0, False
Set WshShell = Nothing