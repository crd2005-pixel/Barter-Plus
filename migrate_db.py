import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "barterplus.db")

def migrate():
    print(f"[*] Conectando a {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("[-] Base de datos no encontrada. Ejecute init_db.py primero si es una instalación limpia.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("[*] Agregando columna 'stock_actual'...")
        cursor.execute("ALTER TABLE productos ADD COLUMN stock_actual FLOAT DEFAULT 0.0")
    except sqlite3.OperationalError as e:
        print(f"[-] Nota: {e}")

    try:
        print("[*] Agregando columna 'es_granel'...")
        cursor.execute("ALTER TABLE productos ADD COLUMN es_granel BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError as e:
        print(f"[-] Nota: {e}")

    try:
        print("[*] Agregando columna 'divisor_granel'...")
        cursor.execute("ALTER TABLE productos ADD COLUMN divisor_granel FLOAT DEFAULT 1.0")
    except sqlite3.OperationalError as e:
        print(f"[-] Nota: {e}")

    # Migrar datos: mover stock de stock_maximo a stock_actual
    print("[*] Migrando datos de stock_maximo a stock_actual...")
    cursor.execute("UPDATE productos SET stock_actual = stock_maximo WHERE stock_maximo > 0")

    # Limpiar stock_maximo si se desea (opcional, por ahora lo dejamos como estaba pero con el valor migrado)
    # cursor.execute("UPDATE productos SET stock_maximo = 0.0")

    conn.commit()
    conn.close()
    print("[+] Migración completada exitosamente.")

if __name__ == "__main__":
    migrate()
