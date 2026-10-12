import sys
import os
import streamlit.web.cli as stcli
import webbrowser
from threading import Timer

# Redireccion de stdout/stderr para evitar crash de Streamlit en modo --noconsole de PyInstaller
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

def open_browser():
    webbrowser.open_new("http://localhost:8501")

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        app_path = os.path.join(sys._MEIPASS, 'app.py')
    else:
        app_path = 'app.py'

    sys.argv = ["streamlit", "run", app_path, "--server.headless=true", "--global.developmentMode=false"]

    # Lanzar navegador manualmente con ligero retraso para dar tiempo a que arranque el servidor
    Timer(2.0, open_browser).start()

    sys.exit(stcli.main())
