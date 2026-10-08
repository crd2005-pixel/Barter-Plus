import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Configuramos la ruta absoluta de la base de datos para evitar problemas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "barterplus.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

import sqlite3
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if table exists before altering
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='productos'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(productos)")
        columnas = [info[1] for info in cursor.fetchall()]

        if "codigo_proveedor" not in columnas:
            cursor.execute("ALTER TABLE productos ADD COLUMN codigo_proveedor TEXT")

        if "equivalencias" not in columnas:
            cursor.execute("ALTER TABLE productos ADD COLUMN equivalencias TEXT")

        conn.commit()
except sqlite3.Error as e:
    print(f"Error de migración: {e}")
finally:
    if 'conn' in locals() and conn:
        conn.close()



# Configuración del motor (engine)
# echo=False para evitar loggear todas las queries en producción
engine = create_engine(DATABASE_URL, echo=False)

# Configuración de la sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base declarativa para los modelos (Sintaxis SQLAlchemy 2.0)
class Base(DeclarativeBase):
    pass

def get_session():
    """Genera una nueva sesión para interactuar con la base de datos."""
    return SessionLocal()
