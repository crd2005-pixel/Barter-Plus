# configuracion.py
# ===========================
# Pestaña de Configuración con acción para inicializar DB
# ===========================

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox
from init_db import init_database


class ConfiguracionTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<h3>Configuración</h3>"))
        layout.addWidget(QLabel("Desde aquí podés inicializar la base de datos y cargar datos básicos."))

        # Botón para correr init_db.py
        btn_init = QPushButton("🔄 Inicializar Base de Datos")
        btn_init.clicked.connect(self.confirm_init_db)
        layout.addWidget(btn_init)

        self.setLayout(layout)

    def confirm_init_db(self):
        reply = QMessageBox.question(
            self,
            "Confirmación",
            "⚠️ ¿Seguro que querés inicializar la base de datos?\n\n"
            "👉 Esto no borra datos existentes, solo asegura que todas las tablas y columnas estén creadas.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.run_init_db()

    def run_init_db(self):
        try:
            init_database()
            QMessageBox.information(self, "Inicialización completa",
                                    "Base de datos inicializada correctamente ✅")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo inicializar la DB:\n{e}")
