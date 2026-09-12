from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt
from services.gastos_service import GastosService

class GastosView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.cargar_datos()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Título
        lbl_titulo = QLabel("Gestión de Gastos Operativos (OPEX)")
        lbl_titulo.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(lbl_titulo)

        # Formulario de Ingreso
        form_lay = QFormLayout()

        self.combo_categoria = QComboBox()
        self.combo_categoria.addItems(["Impuestos", "Sueldos", "Servicios (Luz, Agua, Internet)", "Alquiler", "Limpieza e Insumos", "Mantenimiento", "Varios"])

        self.txt_desc = QLineEdit()
        self.txt_desc.setPlaceholderText("Descripción breve o Nº Comprobante")

        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setRange(0.01, 99999999.0)
        self.spin_monto.setPrefix("$ ")

        form_lay.addRow("Categoría:", self.combo_categoria)
        form_lay.addRow("Descripción / Comprobante:", self.txt_desc)
        form_lay.addRow("Monto Total:", self.spin_monto)

        self.btn_guardar = QPushButton("Registrar Salida de Dinero")
        self.btn_guardar.setStyleSheet("background-color: #d35400; color: white; font-weight: bold; padding: 10px;")
        self.btn_guardar.clicked.connect(self.guardar_gasto)
        form_lay.addRow(self.btn_guardar)

        layout.addLayout(form_lay)

        # Historial del Mes
        lbl_historial = QLabel("Historial de Gastos del Mes Actual")
        lbl_historial.setStyleSheet("font-weight: bold; margin-top: 15px;")
        layout.addWidget(lbl_historial)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Fecha", "Categoría", "Descripción", "Monto Extraído"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.table)

    def guardar_gasto(self):
        desc = self.txt_desc.text().strip()
        if not desc:
            QMessageBox.warning(self, "Error", "Debe ingresar una descripción del gasto.")
            return

        monto = self.spin_monto.value()
        cat = self.combo_categoria.currentText()

        try:
            GastosService.registrar_gasto(cat, desc, monto)
            QMessageBox.information(self, "Éxito", f"Gasto registrado exitosamente.\n\nSe extrajeron ${monto:.2f} de la Caja Activa.")
            self.txt_desc.clear()
            self.spin_monto.setValue(0.0)
            self.cargar_datos()
        except Exception as e:
            QMessageBox.critical(self, "Error Contable", str(e))

    def cargar_datos(self):
        gastos = GastosService.obtener_gastos_del_mes()
        self.table.setRowCount(len(gastos))

        for row, g in enumerate(gastos):
            self.table.setItem(row, 0, QTableWidgetItem(g.fecha.strftime("%Y-%m-%d %H:%M")))
            self.table.setItem(row, 1, QTableWidgetItem(g.categoria))
            self.table.setItem(row, 2, QTableWidgetItem(g.descripcion))

            i_monto = QTableWidgetItem(f"${g.monto:.2f}")
            i_monto.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 3, i_monto)

    def showEvent(self, event):
        super().showEvent(event)
        self.cargar_datos()
