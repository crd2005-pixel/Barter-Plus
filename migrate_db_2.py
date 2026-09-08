import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "barterplus.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE ventas ADD COLUMN tipo_comprobante VARCHAR DEFAULT 'Remito'")
        cursor.execute("ALTER TABLE detalle_ventas ADD COLUMN descuento_unitario FLOAT DEFAULT 0.0")
    except Exception as e:
        print(f"Nota: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
