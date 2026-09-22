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
                conn.commit()
            except Exception:
                pass # Probablemente la columna ya exista

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
