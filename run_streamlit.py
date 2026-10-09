import os
import sys
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

def main():
    if getattr(sys, 'frozen', False):
        script_dir = sys._MEIPASS
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))

    app_path = os.path.join(script_dir, 'app.py')

    sys.argv = ["streamlit", "run", app_path, "--server.headless", "true", "--global.developmentMode", "false"]

    # Lanzar navegador manualmente con ligero retraso para dar tiempo a que arranque el servidor
    Timer(2.0, open_browser).start()

    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
