import os
from database.conexion import engine, Base, DB_PATH
# Importamos todos los modelos para que Base.metadata los reconozca
import database.models

def init_db():
    print(f"[*] Iniciando creación de base de datos en: {DB_PATH}")

    # Crea todas las tablas definidas en los modelos que heredan de Base
    Base.metadata.create_all(bind=engine)

    # Verificación simple
    if os.path.exists(DB_PATH):
        print("[+] Base de datos creada exitosamente.")
        # Opcional: imprimir las tablas creadas
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tablas = inspector.get_table_names()
        print(f"[+] Tablas creadas ({len(tablas)}):")
        for tabla in tablas:
            print(f"    - {tabla}")
    else:
        print("[-] Error: No se pudo crear el archivo de base de datos.")

if __name__ == "__main__":
    init_db()
