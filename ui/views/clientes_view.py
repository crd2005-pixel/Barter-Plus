from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QCheckBox
)
from PyQt6.QtCore import Qt
from services.cliente_service import ClienteService

class EditarClienteDialog(QDialog):
    def __init__(self, cliente, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Cliente")
        self.cliente = cliente
        self.setup_ui()
        self.cargar_datos()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_nombre = QLineEdit()
        self.txt_dni = QLineEdit()
        self.txt_celular = QLineEdit()
        self.txt_direccion = QLineEdit()
        self.txt_email = QLineEdit()
        self.chk_especial = QCheckBox("Es Cliente VIP (Aplica descuentos 10%)")

        form.addRow("Nombre/Razón Social (*):", self.txt_nombre)
        form.addRow("DNI/CUIT:", self.txt_dni)
        form.addRow("Celular:", self.txt_celular)
        form.addRow("Dirección:", self.txt_direccion)
        form.addRow("Email:", self.txt_email)
        form.addRow("", self.chk_especial)

        layout.addLayout(form)

        btn_lay = QHBoxLayout()
        btn_guardar = QPushButton("Guardar Cambios")
        btn_guardar.setStyleSheet("background-color: #0275d8; color: white; font-weight: bold;")
        btn_cancelar = QPushButton("Cancelar")

        btn_guardar.clicked.connect(self.guardar)
        btn_cancelar.clicked.connect(self.reject)

        btn_lay.addWidget(btn_guardar)
        btn_lay.addWidget(btn_cancelar)
        layout.addLayout(btn_lay)

    def cargar_datos(self):
        self.txt_nombre.setText(self.cliente.nombre)
        if self.cliente.dni: self.txt_dni.setText(self.cliente.dni)
        if self.cliente.telefono: self.txt_celular.setText(self.cliente.telefono)
        if self.cliente.direccion: self.txt_direccion.setText(self.cliente.direccion)
        if self.cliente.email: self.txt_email.setText(self.cliente.email)
        self.chk_especial.setChecked(self.cliente.es_especial)

    def guardar(self):
        nombre = self.txt_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Error", "El nombre es obligatorio.")
            return

        try:
            ClienteService.actualizar_cliente(
                cliente_id=self.cliente.id,
                nombre=nombre,
                dni=self.txt_dni.text().strip() or None,
                telefono=self.txt_celular.text().strip() or None,
                direccion=self.txt_direccion.text().strip() or None,
                email=self.txt_email.text().strip() or None,
                es_especial=self.chk_especial.isChecked()
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo actualizar el cliente:\\n{e}")

class ClientesView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.cargar_datos()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Cabecera
        header_lay = QHBoxLayout()
        lbl_titulo = QLabel("Maestro de Clientes")
        lbl_titulo.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.btn_recargar = QPushButton("Actualizar Lista")
        self.btn_recargar.clicked.connect(self.cargar_datos)

        header_lay.addWidget(lbl_titulo)
        header_lay.addStretch()
        header_lay.addWidget(self.btn_recargar)
        layout.addLayout(header_lay)

        # Grilla
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre / Razón Social", "DNI/CUIT", "Teléfono", "Email", "Dirección", "Tipo"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self.editar_cliente)

        layout.addWidget(self.table)

    def cargar_datos(self):
        self.clientes = ClienteService.listar_todos()
        self.table.setRowCount(len(self.clientes))

        for row, c in enumerate(self.clientes):
            self.table.setItem(row, 0, QTableWidgetItem(str(c.id)))
            self.table.setItem(row, 1, QTableWidgetItem(c.nombre))
            self.table.setItem(row, 2, QTableWidgetItem(c.dni or "-"))
            self.table.setItem(row, 3, QTableWidgetItem(c.telefono or "-"))
            self.table.setItem(row, 4, QTableWidgetItem(c.email or "-"))
            self.table.setItem(row, 5, QTableWidgetItem(c.direccion or "-"))

            i_tipo = QTableWidgetItem("VIP (Descuento 10%)" if c.es_especial else "Regular")
            if c.es_especial:
                i_tipo.setForeground(Qt.GlobalColor.darkYellow)
                font = i_tipo.font()
                font.setBold(True)
                i_tipo.setFont(font)
            self.table.setItem(row, 6, i_tipo)

    def editar_cliente(self):
        row = self.table.currentRow()
        if row < 0: return

        cliente_id_str = self.table.item(row, 0).text()
        cliente = next((c for c in self.clientes if str(c.id) == cliente_id_str), None)

        if cliente:
            dialog = EditarClienteDialog(cliente, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.cargar_datos()

    def showEvent(self, event):
        super().showEvent(event)
        self.cargar_datos()
