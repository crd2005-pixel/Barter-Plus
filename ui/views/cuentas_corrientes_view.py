from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt
from services.cuenta_corriente_service import CuentaCorrienteService
from database.conexion import get_session
from database.models.cliente import Cliente
from database.models.proveedor import Proveedor

class TabCuentasBase(QWidget):
    def __init__(self, tipo_entidad="Cliente"):
        super().__init__()
        self.tipo_entidad = tipo_entidad
        self.entidades = []
        self._setup_ui()
        self._cargar_entidades()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header Selector
        h_layout = QHBoxLayout()
        self.lbl_selector = QLabel(f"Seleccionar {self.tipo_entidad}:")
        self.cmb_entidad = QComboBox()
        self.cmb_entidad.setMinimumWidth(300)
        self.cmb_entidad.currentIndexChanged.connect(self._on_entidad_seleccionada)

        h_layout.addWidget(self.lbl_selector)
        h_layout.addWidget(self.cmb_entidad)
        h_layout.addStretch()
        layout.addLayout(h_layout)

        # Panel de Saldo
        self.lbl_saldo = QLabel("Saldo Actual: $ 0.00")
        self.lbl_saldo.setStyleSheet("font-size: 28px; font-weight: bold; color: #2E86C1; margin: 15px 0;")
        layout.addWidget(self.lbl_saldo, alignment=Qt.AlignmentFlag.AlignCenter)

        # Grilla Historial
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Fecha", "Concepto", "Debe", "Haber", "Saldo"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self._mostrar_detalle_movimiento)
        layout.addWidget(self.table)

        # Botón Acción
        self.btn_accion = QPushButton("Registrar Cobro" if self.tipo_entidad == "Cliente" else "Registrar Pago")
        self.btn_accion.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; height: 40px; font-size: 14px;")
        self.btn_accion.clicked.connect(self._registrar_movimiento)
        layout.addWidget(self.btn_accion)

    def _cargar_entidades(self):
        self.cmb_entidad.blockSignals(True)
        self.cmb_entidad.clear()
        self.entidades.clear()
        self.cmb_entidad.addItem(f"-- Seleccione {self.tipo_entidad} --", None)

        with get_session() as session:
            if self.tipo_entidad == "Cliente":
                datos = session.query(Cliente).order_by(Cliente.nombre).all()
            else:
                datos = session.query(Proveedor).order_by(Proveedor.nombre).all()

            for d in datos:
                self.entidades.append(d)
                self.cmb_entidad.addItem(d.nombre, d.id)

        self.cmb_entidad.blockSignals(False)

    def _on_entidad_seleccionada(self):
        entidad_id = self.cmb_entidad.currentData()
        if not entidad_id:
            self.table.setRowCount(0)
            self.lbl_saldo.setText("Saldo Actual: $ 0.00")
            return

        self._cargar_historial(entidad_id)

    def _cargar_historial(self, entidad_id):
        self.table.setRowCount(0)
        self.table.clearContents()

        if self.tipo_entidad == "Cliente":
            movimientos = CuentaCorrienteService.obtener_historial_cliente(entidad_id)
            saldo_actual = CuentaCorrienteService.obtener_saldo_cliente(entidad_id)
        else:
            movimientos = CuentaCorrienteService.obtener_historial_proveedor(entidad_id)
            saldo_actual = CuentaCorrienteService.obtener_saldo_proveedor(entidad_id)

        self.table.setRowCount(len(movimientos))
        for r, m in enumerate(movimientos):
            item_fecha = QTableWidgetItem(m['fecha'].strftime("%d/%m/%Y %H:%M"))
            if 'venta_id' in m and m['venta_id']:
                item_fecha.setData(Qt.ItemDataRole.UserRole, m['venta_id'])
            self.table.setItem(r, 0, item_fecha)
            self.table.setItem(r, 1, QTableWidgetItem(m['concepto']))
            self.table.setItem(r, 2, QTableWidgetItem(f"$ {m['debe']:.2f}"))
            self.table.setItem(r, 3, QTableWidgetItem(f"$ {m['haber']:.2f}"))

            item_saldo = QTableWidgetItem(f"$ {m['saldo']:.2f}")
            if m['saldo'] > 0:
                item_saldo.setForeground(Qt.GlobalColor.red)
            elif m['saldo'] < 0:
                item_saldo.setForeground(Qt.GlobalColor.darkGreen)

            self.table.setItem(r, 4, item_saldo)

        color_saldo = "red" if saldo_actual > 0 else ("green" if saldo_actual < 0 else "#2E86C1")
        self.lbl_saldo.setText(f"Saldo Actual: $ {saldo_actual:.2f}")
        self.lbl_saldo.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {color_saldo}; margin: 15px 0;")

    def _mostrar_detalle_movimiento(self, row, col):
        item_fecha = self.table.item(row, 0)
        if not item_fecha: return
        venta_id = item_fecha.data(Qt.ItemDataRole.UserRole)
        if not venta_id: return

        from PyQt6.QtWidgets import QDialog, QTableWidget, QTableWidgetItem, QVBoxLayout, QHeaderView
        from database.conexion import get_session
        from database.models.venta import DetalleVenta

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Detalle de Venta #{venta_id}")
        dlg.resize(600, 400)
        dlg_layout = QVBoxLayout(dlg)

        tabla_detalle = QTableWidget()
        tabla_detalle.setColumnCount(4)
        tabla_detalle.setHorizontalHeaderLabels(["Producto", "Cantidad", "Precio Unitario", "Subtotal"])
        tabla_detalle.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        dlg_layout.addWidget(tabla_detalle)

        with get_session() as session:
            detalles = session.query(DetalleVenta).filter(DetalleVenta.venta_id == venta_id).all()
            tabla_detalle.setRowCount(len(detalles))
            for i, det in enumerate(detalles):
                tabla_detalle.setItem(i, 0, QTableWidgetItem(det.descripcion))
                tabla_detalle.setItem(i, 1, QTableWidgetItem(f"{det.cantidad:.2f}"))
                tabla_detalle.setItem(i, 2, QTableWidgetItem(f"$ {det.precio_unitario:.2f}"))
                tabla_detalle.setItem(i, 3, QTableWidgetItem(f"$ {det.subtotal:.2f}"))

        dlg.exec()

    def _registrar_movimiento(self):
        entidad_id = self.cmb_entidad.currentData()
        if not entidad_id:
            QMessageBox.warning(self, "Atención", f"Debe seleccionar un {self.tipo_entidad}.")
            return

        monto, ok1 = QInputDialog.getDouble(self, "Registrar Movimiento", "Monto ($):", 0, 0, 999999999, 2)
        if not ok1 or monto <= 0: return

        concepto, ok2 = QInputDialog.getText(self, "Registrar Movimiento", "Concepto / Descripción:")
        if not ok2 or not concepto.strip(): return

        try:
            if self.tipo_entidad == "Cliente":
                # Cobro a un cliente (Haber para la cuenta del cliente, disminuye deuda)
                CuentaCorrienteService.registrar_movimiento_cliente(
                    cliente_id=entidad_id, concepto=concepto.strip(), debe=0.0, haber=monto
                )
            else:
                # Pago a un proveedor (Haber para la cuenta del proveedor, disminuye deuda)
                CuentaCorrienteService.registrar_movimiento_proveedor(
                    proveedor_id=entidad_id, concepto=concepto.strip(), debe=0.0, haber=monto
                )

            QMessageBox.information(self, "Éxito", "Movimiento registrado correctamente.")
            self._cargar_historial(entidad_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al registrar: {str(e)}")

    def showEvent(self, event):
        super().showEvent(event)
        # Recargar entidades sin perder la selección actual
        current_id = self.cmb_entidad.currentData()
        self._cargar_entidades()
        if current_id:
            idx = self.cmb_entidad.findData(current_id)
            if idx >= 0:
                self.cmb_entidad.blockSignals(True)
                self.cmb_entidad.setCurrentIndex(idx)
                self.cmb_entidad.blockSignals(False)
                # Forzar recarga una única vez para este registro
                self._cargar_historial(current_id)


class CuentasCorrientesTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tab_clientes = TabCuentasBase(tipo_entidad="Cliente")
        self.tab_proveedores = TabCuentasBase(tipo_entidad="Proveedor")

        self.tabs.addTab(self.tab_clientes, "Deudas de Clientes")
        self.tabs.addTab(self.tab_proveedores, "Deudas con Proveedores")

        layout.addWidget(self.tabs)
