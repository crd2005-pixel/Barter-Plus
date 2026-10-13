Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c python -m streamlit run app.py", 0, False
Set WshShell = Nothing
