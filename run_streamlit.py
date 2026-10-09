import os
import sys
import streamlit.web.cli as stcli

def main():
    if getattr(sys, 'frozen', False):
        script_dir = sys._MEIPASS
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))

    app_path = os.path.join(script_dir, 'app.py')

    sys.argv = ["streamlit", "run", app_path, "--server.headless", "false", "--global.developmentMode", "false"]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
