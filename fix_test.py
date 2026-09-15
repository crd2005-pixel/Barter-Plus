import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "barterplus.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("DELETE FROM productos WHERE codigo_barras = '1234567890'")
conn.commit()
conn.close()
