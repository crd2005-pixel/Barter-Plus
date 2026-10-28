import sqlite3
import os
import json

def get_unificador_dir():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = os.path.expanduser("~")

    unificador_dir = os.path.join(appdata, "BarterPlus_Unificador")
    if not os.path.exists(unificador_dir):
        os.makedirs(unificador_dir, exist_ok=True)
    return unificador_dir

def get_barterplus_db_path():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = os.path.expanduser("~")
    return os.path.join(appdata, "BarterPlus", "barterplus.db")

def get_readonly_connection():
    db_path = get_barterplus_db_path()
    # Si la base de datos principal no existe, devuelve None (puede no estar instalado en este PC)
    if not os.path.exists(db_path):
        return None

    try:
        # Modo solo lectura estricto URI SQLite
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        return conn
    except sqlite3.Error as e:
        registrar_error_seguro(f"Error conectando a barterplus.db en modo solo lectura: {e}")
        return None

def registrar_error_seguro(msg):
    try:
        unificador_dir = get_unificador_dir()
        log_path = os.path.join(unificador_dir, "error_log.txt")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass # Nunca interrumpir el flujo principal

def load_config():
    try:
        unificador_dir = get_unificador_dir()
        config_path = os.path.join(unificador_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        registrar_error_seguro(f"Error cargando config: {e}")
    return {}

def save_config(config_data):
    try:
        unificador_dir = get_unificador_dir()
        config_path = os.path.join(unificador_dir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        registrar_error_seguro(f"Error guardando config: {e}")

def get_internal_db_connection():
    try:
        unificador_dir = get_unificador_dir()
        internal_db = os.path.join(unificador_dir, "unificador_interno.db")
        conn = sqlite3.connect(internal_db)
        return conn
    except Exception as e:
        registrar_error_seguro(f"Error conectando a unificador_interno.db: {e}")
        return None
