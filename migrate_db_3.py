import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "barterplus.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE clientes ADD COLUMN es_especial BOOLEAN DEFAULT 0")
        print("Columna 'es_especial' agregada a la tabla clientes.")
    except Exception as e:
        print(f"Nota: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
