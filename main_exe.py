import subprocess
import sys
import os

def main():
    # Determinar ruta base
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    app_script = os.path.join(base_dir, 'app.py')

    # Ejecutar Streamlit como subproceso usando el Python del bundle
    comando = [
        sys.executable, "-m", "streamlit", "run",
        app_script,
        "--server.port=8501",
        "--server.headless=false",
        "--global.developmentMode=false"
    ]

    subprocess.run(comando, env=os.environ.copy())

if __name__ == '__main__':
    main()
