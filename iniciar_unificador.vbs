Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = currentDir

' Ejecutar el servidor Streamlit en modo oculto
WshShell.Run "cmd /c python -m streamlit run app.py --server.headless true > error_log.txt 2>&1", 0, False

' Esperar 3 segundos a que el servidor levante
WScript.Sleep 3000

' Abrir el navegador en el puerto por defecto
WshShell.Run "http://localhost:8501"

Set WshShell = Nothing
Set fso = Nothing
