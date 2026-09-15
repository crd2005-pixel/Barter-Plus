import sqlite3
import os

DB_PATH = "barterplus.db"

def apply_patch():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute('ALTER TABLE ingresos_diferidos ADD COLUMN lote VARCHAR(50);')
        print("Added column 'lote' to 'ingresos_diferidos'.")
    except sqlite3.OperationalError as e:
        print(f"Skipping lote: {e}")

    try:
        cursor.execute('ALTER TABLE ingresos_diferidos ADD COLUMN cupon VARCHAR(50);')
        print("Added column 'cupon' to 'ingresos_diferidos'.")
    except sqlite3.OperationalError as e:
        print(f"Skipping cupon: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    apply_patch()
