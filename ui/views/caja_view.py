from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog, QDialog, QFormLayout, QLineEdit, QComboBox, QTabWidget
)
from PyQt6.QtCore import Qt
from services.caja_service import CajaService

class MovimientoDialog(QDialog):
    def __init__(self, tipo: str, parent=None):
        super().__init__(parent)
        self.tipo = tipo
        self.setWindowTitle(f"Registrar {tipo}")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.txt_concepto = QLineEdit()
        self.txt_monto = QLineEdit()
        self.combo_metodo = QComboBox()
        self.combo_metodo.addItems(["Efectivo", "Tarjeta", "Transferencia"])

        layout.addRow("Concepto:", self.txt_concepto)
        layout.addRow("Monto ($):", self.txt_monto)
        layout.addRow("Método:", self.combo_metodo)

        btn_layout = QHBoxLayout()
        btn_guardar = QPushButton("Guardar")
        btn_guardar.clicked.connect(self.accept)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)

        btn_layout.addWidget(btn_guardar)
        btn_layout.addWidget(btn_cancelar)
        layout.addRow(btn_layout)

    def get_data(self):
        try:
            monto = float(self.txt_monto.text().strip())
        except ValueError:
            monto = 0.0
        return self.txt_concepto.text().strip(), monto, self.combo_metodo.currentText()

class CajaActualTab(QWidget):
    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view
        self.caja_activa = None
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Panel Superior
        header_layout = QHBoxLayout()
        self.lbl_estado = QLabel("Estado: DESCONOCIDO")
        self.lbl_estado.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.lbl_saldo = QLabel("Saldo Actual (Efectivo): $0.00")
        self.lbl_saldo.setStyleSheet("font-size: 24px; font-weight: bold; color: green;")

        header_layout.addWidget(self.lbl_estado)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_saldo)

        main_layout.addLayout(header_layout)

        # Botonera
        btn_layout = QHBoxLayout()
        self.btn_abrir = QPushButton("Abrir Caja")
        self.btn_abrir.clicked.connect(self.abrir_caja)

        self.btn_cerrar = QPushButton("Cerrar Caja (Auditoría)")
        self.btn_cerrar.clicked.connect(self.cerrar_caja)
        self.btn_cerrar.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold;")

        self.btn_ingreso = QPushButton("Ingreso de Dinero")
        self.btn_ingreso.clicked.connect(self.registrar_ingreso)

        self.btn_retiro = QPushButton("Retiro de Dinero")
        self.btn_retiro.clicked.connect(self.registrar_retiro)

        btn_layout.addWidget(self.btn_abrir)
        btn_layout.addWidget(self.btn_cerrar)
        btn_layout.addWidget(self.btn_ingreso)
        btn_layout.addWidget(self.btn_retiro)

        main_layout.addLayout(btn_layout)

        # Grilla de Movimientos
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Hora", "Tipo", "Descripción", "Método", "Ingreso", "Egreso", "Saldo Parcial"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        main_layout.addWidget(self.table)

    def refresh_caja(self):
        self.caja_activa = CajaService.obtener_caja_activa()
        if self.caja_activa:
            self.lbl_estado.setText("Estado: ABIERTA")
            self.lbl_estado.setStyleSheet("font-size: 24px; font-weight: bold; color: green;")
            saldo = CajaService.calcular_saldo_efectivo(self.caja_activa.id)
            self.lbl_saldo.setText("Saldo Actual (Efectivo): ****** [Oculto por Auditoría]")

            self.btn_abrir.setEnabled(False)
            self.btn_cerrar.setEnabled(True)
            self.btn_ingreso.setEnabled(True)
            self.btn_retiro.setEnabled(True)

            self.cargar_movimientos()
        else:
            self.lbl_estado.setText("Estado: CERRADA")
            self.lbl_estado.setStyleSheet("font-size: 24px; font-weight: bold; color: red;")
            self.lbl_saldo.setText("Saldo Actual (Efectivo): $0.00")

            self.btn_abrir.setEnabled(True)
            self.btn_cerrar.setEnabled(False)
            self.btn_ingreso.setEnabled(False)
            self.btn_retiro.setEnabled(False)

            self.table.setRowCount(0)

    def cargar_movimientos(self):
        if not self.caja_activa:
            return

        movimientos = CajaService.obtener_movimientos(self.caja_activa.id)
        self.table.setRowCount(len(movimientos))

        saldo_parcial = 0.0

        for row, mov in enumerate(movimientos):
            if mov.metodo == "Efectivo":
                if mov.tipo == "Ingreso":
                    saldo_parcial += mov.monto
                else:
                    saldo_parcial -= mov.monto

            hora_str = mov.fecha.strftime("%H:%M:%S")
            self.table.setItem(row, 0, QTableWidgetItem(hora_str))
            self.table.setItem(row, 1, QTableWidgetItem(mov.tipo))
            self.table.setItem(row, 2, QTableWidgetItem(mov.concepto))
            self.table.setItem(row, 3, QTableWidgetItem(mov.metodo))

            if mov.tipo == "Ingreso":
                self.table.setItem(row, 4, QTableWidgetItem(f"${mov.monto:.2f}"))
                self.table.setItem(row, 5, QTableWidgetItem("-"))
            else:
                self.table.setItem(row, 4, QTableWidgetItem("-"))
                self.table.setItem(row, 5, QTableWidgetItem(f"${mov.monto:.2f}"))

            self.table.setItem(row, 6, QTableWidgetItem(f"${saldo_parcial:.2f}"))

        self.table.scrollToBottom()

    def abrir_caja(self):
        monto, ok = QInputDialog.getDouble(
            self, "Abrir Caja", "Ingrese monto inicial de cambio ($):", 0, 0, 10000000, 2
        )
        if ok:
            try:
                CajaService.abrir_caja(monto)
                QMessageBox.information(self, "Caja", "Caja abierta exitosamente.")
                self.parent_view.refresh_all()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def cerrar_caja(self):
        if not self.caja_activa:
            return

        monto_real, ok = QInputDialog.getDouble(
            self, "Cerrar Caja (Auditoría)",
            "Atención: Ingrese el MONTO FÍSICO REAL en efectivo que tiene en sus manos.\n\n"
            "Monto Físico Declarado ($):", 0, 0, 100000000, 2
        )
        if ok:
            try:
                caja_cerrada = CajaService.cerrar_caja(self.caja_activa.id, monto_real)

                if caja_cerrada.diferencia < 0:
                    QMessageBox.warning(self, "Auditoría de Caja",
                                      f"Caja cerrada.\n¡ATENCIÓN! Se ha detectado un FALTANTE de ${abs(caja_cerrada.diferencia):.2f}.\n"
                                      f"El sistema esperaba ${caja_cerrada.saldo_final_esperado:.2f} pero se declararon ${monto_real:.2f}.\n\n"
                                      "Este movimiento ha quedado registrado de manera inalterable.")
                elif caja_cerrada.diferencia > 0:
                    QMessageBox.information(self, "Auditoría de Caja",
                                      f"Caja cerrada.\nSe ha detectado un SOBRANTE de ${caja_cerrada.diferencia:.2f}.\n"
                                      f"El sistema esperaba ${caja_cerrada.saldo_final_esperado:.2f} pero se declararon ${monto_real:.2f}.\n\n"
                                      "Este movimiento ha quedado registrado de manera inalterable.")
                else:
                    QMessageBox.information(self, "Caja", "Caja cerrada correctamente. Cuadre exacto.")

                self.parent_view.refresh_all()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def registrar_ingreso(self):
        dialog = MovimientoDialog("Ingreso", self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            concepto, monto, metodo = dialog.get_data()
            if concepto and monto > 0:
                try:
                    CajaService.registrar_movimiento(self.caja_activa.id, "Ingreso", concepto, monto, metodo)
                    self.parent_view.refresh_all()
                except Exception as e:
                    QMessageBox.critical(self, "Error", str(e))
            else:
                QMessageBox.warning(self, "Validación", "Debe ingresar un concepto y un monto válido mayor a 0.")

    def registrar_retiro(self):
        dialog = MovimientoDialog("Egreso", self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            concepto, monto, metodo = dialog.get_data()
            if concepto and monto > 0:
                try:
                    CajaService.registrar_movimiento(self.caja_activa.id, "Egreso", concepto, monto, metodo)
                    self.parent_view.refresh_all()
                except Exception as e:
                    QMessageBox.critical(self, "Error", str(e))
            else:
                QMessageBox.warning(self, "Validación", "Debe ingresar un concepto y un monto válido mayor a 0.")

class HistorialCajaTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.btn_refresh = QPushButton("Actualizar Historial")
        self.btn_refresh.clicked.connect(self.cargar_historial)
        layout.addWidget(self.btn_refresh)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "ID Caja", "Fecha Apertura", "Fecha Cierre", "Saldo Inicial",
            "Saldo Final (Sistema)", "Saldo Físico (Declarado)", "Diferencia", "Estado"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.table)

    def cargar_historial(self):
        cajas = CajaService.obtener_historial_cajas()
        self.table.setRowCount(len(cajas))

        for row, caja in enumerate(cajas):
            self.table.setItem(row, 0, QTableWidgetItem(str(caja.id)))

            apertura_str = caja.fecha_apertura.strftime("%Y-%m-%d %H:%M:%S")
            self.table.setItem(row, 1, QTableWidgetItem(apertura_str))

            cierre_str = caja.fecha_cierre.strftime("%Y-%m-%d %H:%M:%S") if caja.fecha_cierre else "-"
            self.table.setItem(row, 2, QTableWidgetItem(cierre_str))

            self.table.setItem(row, 3, QTableWidgetItem(f"${caja.saldo_inicial:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"${caja.saldo_final_esperado:.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"${caja.saldo_final_real:.2f}"))

            item_dif = QTableWidgetItem(f"${caja.diferencia:.2f}")
            if caja.diferencia < 0:
                item_dif.setForeground(Qt.GlobalColor.red)
            elif caja.diferencia > 0:
                item_dif.setForeground(Qt.GlobalColor.blue)
            self.table.setItem(row, 6, item_dif)

            item_estado = QTableWidgetItem(caja.estado)
            if caja.estado == "Abierta":
                item_estado.setForeground(Qt.GlobalColor.darkGreen)
            self.table.setItem(row, 7, item_estado)

class CajaView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.refresh_all()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.tab_actual = CajaActualTab(self)
        self.tab_historial = HistorialCajaTab()

        self.tabs.addTab(self.tab_actual, "Caja Actual")
        self.tabs.addTab(self.tab_historial, "Historial / Auditoría")

        layout.addWidget(self.tabs)

    def refresh_all(self):
        self.tab_actual.refresh_caja()
        self.tab_historial.cargar_historial()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_all()
