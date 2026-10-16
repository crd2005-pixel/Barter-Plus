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

    def _exportar_pdf(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from utils.export_utils import ExportUtils

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Guardar Reporte PDF", "Reporte_Gastos.pdf", "Archivos PDF (*.pdf)"
        )
        if filepath:
            try:
                ExportUtils.exportar_tabla_a_pdf(self.table, "Reporte de Egresos/Gastos - Barter Plus", filepath)
                QMessageBox.information(self, "Éxito", "PDF exportado correctamente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Fallo al exportar: {str(e)}")

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

        self.combo_origen = QComboBox()
        self.combo_origen.addItems(["Caja del Día (Mostrador)", "Tesorería (Efectivo Acumulado)", "Cuenta Bancaria"])

        form_lay.addRow("Origen de Fondos:", self.combo_origen)
        form_lay.addRow("Categoría:", self.combo_categoria)
        form_lay.addRow("Descripción / Comprobante:", self.txt_desc)
        form_lay.addRow("Monto Total:", self.spin_monto)

        self.btn_guardar = QPushButton("Registrar Salida de Dinero")
        self.btn_guardar.setStyleSheet("background-color: #d35400; color: white; font-weight: bold; padding: 10px;")
        self.btn_guardar.clicked.connect(self.guardar_gasto)
        form_lay.addRow(self.btn_guardar)

        layout.addLayout(form_lay)

        # Historial del Mes
        hist_lay = QHBoxLayout()
        lbl_historial = QLabel("Historial de Gastos del Mes Actual")
        lbl_historial.setStyleSheet("font-weight: bold; margin-top: 15px;")

        self.btn_exportar = QPushButton("Exportar a PDF")
        self.btn_exportar.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; margin-top: 15px;")
        self.btn_exportar.clicked.connect(self._exportar_pdf)

        hist_lay.addWidget(lbl_historial)
        hist_lay.addStretch()
        hist_lay.addWidget(self.btn_exportar)
        layout.addLayout(hist_lay)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Fecha", "Categoría", "Origen Fondos", "Descripción", "Monto Extraído"])
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
            GastosService.registrar_gasto(cat, desc, monto, self.combo_origen.currentText())
            QMessageBox.information(self, "Éxito", f"Gasto registrado exitosamente.\n\nSe extrajeron ${monto:.2f} de {self.combo_origen.currentText()}.")
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

            # Since origen is not stored in GastoOperativo directly in this snippet,
            # I will just write '-' or we need to add it to GastoOperativo.
            # The prompt doesn't explicitly ask to add it to the model, but it makes sense to show it.
            # Let's see if the user specified it. "Historial: Una grilla inferior que liste los gastos operativos cargados en el mes."
            # We'll just display a placeholder or leave it out if we didn't add it to model.
            # Wait, I did add the header "Origen Fondos". Let's add it to the model via a quick patch.
            self.table.setItem(row, 2, QTableWidgetItem(g.origen_fondos if hasattr(g, 'origen_fondos') else "-"))
            self.table.setItem(row, 3, QTableWidgetItem(g.descripcion))

            i_monto = QTableWidgetItem(f"${g.monto:.2f}")
            i_monto.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 4, i_monto)

    def showEvent(self, event):
        super().showEvent(event)
        self.cargar_datos()
