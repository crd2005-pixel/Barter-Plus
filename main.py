import sys
import os
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

# Inicializar DB antes de arrancar la interfaz
from init_db import init_db

def main():
    # Asegurar que la base de datos existe (solo crea si no existe)
    try:
        init_db()
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
