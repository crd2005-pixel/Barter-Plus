from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox, QPushButton, QMessageBox, QHBoxLayout, QLabel, QDoubleSpinBox
)
from services.cliente_service import ClienteService

class FastClientDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo Cliente Rápido")
        self.nuevo_cliente_id = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_nombre = QLineEdit()
        self.txt_nombre.setPlaceholderText("Nombre y Apellido (Obligatorio)")
        self.txt_dni = QLineEdit()
        self.txt_dni.setPlaceholderText("DNI / CUIT")
        self.txt_celular = QLineEdit()
        self.txt_celular.setPlaceholderText("Teléfono / Celular")
        self.txt_direccion = QLineEdit()
        self.txt_direccion.setPlaceholderText("Dirección")
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("Correo Electrónico")
        self.chk_especial = QCheckBox("Es Cliente VIP (Aplica descuentos 10%)")

        form.addRow("Nombre/Razón Social (*):", self.txt_nombre)
        form.addRow("DNI/CUIT:", self.txt_dni)
        form.addRow("Celular:", self.txt_celular)
        form.addRow("Dirección:", self.txt_direccion)
        form.addRow("Email:", self.txt_email)
        form.addRow("", self.chk_especial)
        layout.addLayout(form)

        self.btn_guardar = QPushButton("Guardar Cliente")
        self.btn_guardar.setStyleSheet("background-color: #0275d8; color: white; font-weight: bold;")
        self.btn_guardar.clicked.connect(self.guardar)
        layout.addWidget(self.btn_guardar)

    def guardar(self):
        if not self.txt_nombre.text().strip():
            QMessageBox.warning(self, "Error", "El nombre es obligatorio")
            return

        try:
            nuevo = ClienteService.crear_cliente(
                nombre=self.txt_nombre.text().strip(),
                dni=self.txt_dni.text().strip() or None,
                telefono=self.txt_celular.text().strip() or None,
                direccion=self.txt_direccion.text().strip() or None,
                email=self.txt_email.text().strip() or None,
                es_especial=self.chk_especial.isChecked()
            )
            self.nuevo_cliente_id = nuevo.id
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo crear: {e}")

class ItemManualDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ítem Manual / Servicio")
        self.data_item = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_desc = QLineEdit()
        self.txt_desc.setPlaceholderText("Ej. Mano de obra, Envío, Servicio...")

        self.spin_cant = QDoubleSpinBox()
        self.spin_cant.setRange(0.01, 99999.0)
        self.spin_cant.setValue(1.0)

        self.spin_precio = QDoubleSpinBox()
        self.spin_precio.setRange(0.01, 9999999.0)
        self.spin_precio.setPrefix("$ ")
        self.spin_precio.setValue(1000.0)

        form.addRow("Descripción:", self.txt_desc)
        form.addRow("Cantidad:", self.spin_cant)
        form.addRow("Precio Unitario:", self.spin_precio)
        layout.addLayout(form)

        self.btn_ok = QPushButton("Añadir al Carrito")
        self.btn_ok.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold;")
        self.btn_ok.clicked.connect(self.agregar)
        layout.addWidget(self.btn_ok)

    def agregar(self):
        if not self.txt_desc.text().strip():
            QMessageBox.warning(self, "Error", "Debe ingresar una descripción.")
            return

        self.data_item = {
            'id': None,
            'codigo': "MAN-001",
            'marca': "Servicio/Manual",
            'nombre': self.txt_desc.text().strip(),
            'precio_base': self.spin_precio.value(),
            'cantidad': self.spin_cant.value(),
            'descuento_unit': 0.0
        }
        self.accept()
