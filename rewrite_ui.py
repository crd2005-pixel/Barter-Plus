import re
import os

with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add APP_DATA_DIR logic at the top (before App class)
app_data_logic = """
APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.dirname(os.path.abspath(__file__))), "BarterPlus_Unificador")
os.makedirs(APP_DATA_DIR, exist_ok=True)
ERROR_LOG_PATH = os.path.join(APP_DATA_DIR, "error_log.txt")
CONFIG_PATH = os.path.join(APP_DATA_DIR, "config.json")

def registrar_error_seguro(mensaje: str):
    import traceback
    try:
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(mensaje + "\\n")
    except Exception:
        pass
"""

# Find imports block and append
imports_end = content.find("PATRON_MEMBRETE")
if imports_end != -1:
    content = content[:imports_end] + app_data_logic + "\n" + content[imports_end:]

# 2. Fix error logs occurrences
content = content.replace("unificador_listas/error_log.txt", "ERROR_LOG_PATH")
content = content.replace("with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'error_log.txt')", "with open(ERROR_LOG_PATH")
content = content.replace("'config.json'", "CONFIG_PATH")

with open('unificador_listas/app_temp.py', 'w', encoding='utf-8') as f:
    f.write(content)
