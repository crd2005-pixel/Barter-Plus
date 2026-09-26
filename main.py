import sys
import os
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    from database.conexion import Base, engine
    from sqlalchemy import text
    # Asegurar que la base de datos existe (solo crea si no existe)
    try:
        Base.metadata.create_all(bind=engine)

        # Parche de migración en caliente
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE cheques ADD COLUMN estado VARCHAR DEFAULT 'Pendiente'"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE cambios_aceite ADD COLUMN qr_token VARCHAR"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE garantias_baterias ADD COLUMN qr_token VARCHAR"))
                conn.commit()
            except Exception:
                pass # Probablemente la columna ya exista

            try:
                conn.execute(text("CREATE TABLE IF NOT EXISTS vehiculos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER NOT NULL, dominio VARCHAR NOT NULL UNIQUE, marca VARCHAR, modelo VARCHAR, anio INTEGER)"))
                conn.execute(text("CREATE TABLE IF NOT EXISTS garantias_baterias (id INTEGER PRIMARY KEY AUTOINCREMENT, vehiculo_id INTEGER NOT NULL, producto_id INTEGER NOT NULL, fecha_instalacion DATE, meses_garantia INTEGER NOT NULL, fecha_vencimiento DATE NOT NULL, codigo_garantia VARCHAR NOT NULL UNIQUE)"))
                conn.execute(text("CREATE TABLE IF NOT EXISTS cambios_aceite (id INTEGER PRIMARY KEY AUTOINCREMENT, vehiculo_id INTEGER NOT NULL, fecha DATE, km_actual INTEGER NOT NULL, proximo_km INTEGER NOT NULL, aceite_utilizado VARCHAR NOT NULL, filtro_aceite BOOLEAN, filtro_aire BOOLEAN, filtro_combustible BOOLEAN, filtro_habitaculo BOOLEAN, observaciones VARCHAR)"))
                conn.commit()
            except Exception:
                pass

    except Exception as e:
        print(f"Error inicializando base de datos: {e}")

    app = QApplication(sys.argv)

    # Aplicar un estilo oscuro y sobrio base
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
