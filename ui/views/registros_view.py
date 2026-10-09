from PyQt6.QtWidgets import (
    QMessageBox,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QTabWidget, QDateEdit, QCompleter, QSplitter
)
from PyQt6.QtCore import Qt, QDate, QStringListModel
from services.registros_service import RegistrosService
from services.cliente_service import ClienteService
import datetime as dt

class RegistroVentasTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.cargar_datos()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Filtros
        filtros_lay = QHBoxLayout()

        self.date_desde = QDateEdit()
        self.date_desde.setCalendarPopup(True)
        self.date_desde.setDate(QDate.currentDate().addDays(-30)) # Últimos 30 días por defecto

        self.date_hasta = QDateEdit()
        self.date_hasta.setCalendarPopup(True)
        self.date_hasta.setDate(QDate.currentDate())

        self.combo_comprobante = QComboBox()
        self.combo_comprobante.addItems(["Todos", "Remito", "Factura"])

        btn_filtrar = QPushButton("Filtrar")
        btn_filtrar.clicked.connect(self.cargar_datos)

        filtros_lay.addWidget(QLabel("Desde:"))
        filtros_lay.addWidget(self.date_desde)
        filtros_lay.addWidget(QLabel("Hasta:"))
        filtros_lay.addWidget(self.date_hasta)
        filtros_lay.addWidget(QLabel("Comprobante:"))
        filtros_lay.addWidget(self.combo_comprobante)
        filtros_lay.addWidget(btn_filtrar)
        self.btn_anular = QPushButton("Anular Comprobante")
        self.btn_anular.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.btn_anular.clicked.connect(self.anular_venta)

        filtros_lay.addWidget(self.btn_anular)

        self.btn_export_v = QPushButton("Exportar")
        self.btn_export_v.clicked.connect(lambda: self._export(self.table))
        filtros_lay.addWidget(self.btn_export_v)

        filtros_lay.addStretch()

        layout.addLayout(filtros_lay)

        # Grilla
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Fecha", "Comprobante", "Cliente", "Total", "Método Pago", "Estado"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._abrir_detalle)

        layout.addWidget(self.table)


    def _abrir_detalle(self, row, col):
        item_f = self.table.item(row, 0)
        if not item_f: return
        venta_id = item_f.data(Qt.ItemDataRole.UserRole)
        if not venta_id: return

        from ui.components.dialogs import DetalleVentaDialog
        dlg = DetalleVentaDialog(venta_id, self)
        dlg.exec()

    def _export(self, tbl):
        from utils.export_utils import ExportUtils
        ExportUtils.exportar_tabla_csv(tbl, self, "Ventas")

    def anular_venta(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Atención", "Debe seleccionar una venta de la lista para anularla.")
            return

        comprobante_txt = self.table.item(row, 1).text()
        try:
            venta_id = int(comprobante_txt.split('#')[-1].strip())
        except:
            QMessageBox.warning(self, "Error", "No se pudo leer el ID del comprobante.")
            return

        estado = self.table.item(row, 5).text() if self.table.columnCount() > 5 else "Completada"
        if estado == "Anulado":
            QMessageBox.information(self, "Aviso", "Esta venta ya está anulada.")
            return

        reply = QMessageBox.question(
            self, "Confirmar Anulación",
            f"¿Está completamente seguro de que desea anular el comprobante {comprobante_txt}?\n\nEsta acción DEVOLVERÁ el stock, GENERARÁ contra-asientos financieros/fiscales y no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                from services.venta_service import VentaService
                VentaService.anular_venta(venta_id)
                QMessageBox.information(self, "Éxito", f"Comprobante {comprobante_txt} anulado exitosamente.")
                self.cargar_datos()
            except Exception as e:
                QMessageBox.critical(self, "Error Fatal", str(e))

    def cargar_datos(self):
        d_desde = self.date_desde.date().toPyDate()
        d_hasta = self.date_hasta.date().toPyDate()
        comp = self.combo_comprobante.currentText()

        ventas = RegistrosService.obtener_ventas(d_desde, d_hasta, comp)
        self.table.setRowCount(len(ventas))

        for row, v in enumerate(ventas):
            f_str = v.fecha.strftime("%Y-%m-%d %H:%M:%S")
            c_nom = v.cliente.nombre if v.cliente else "Consumidor Final"

            item_f = QTableWidgetItem(f_str)
            item_f.setData(Qt.ItemDataRole.UserRole, v.id)
            self.table.setItem(row, 0, item_f)
            self.table.setItem(row, 1, QTableWidgetItem(f"{v.tipo_comprobante} #{v.id}"))
            self.table.setItem(row, 2, QTableWidgetItem(c_nom))
            self.table.setItem(row, 3, QTableWidgetItem(f"${v.total:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(v.metodo_pago))

            i_est = QTableWidgetItem(v.estado)
            if v.estado == "Anulado":
                from PyQt6.QtGui import QColor, QBrush
                for c in range(6):
                    item = self.table.item(row, c)
                    if not item:
                        item = QTableWidgetItem("")
                        self.table.setItem(row, c, item)
                    item.setBackground(QBrush(QColor(231, 76, 60, 50)))
                    item.setForeground(Qt.GlobalColor.darkRed)
            self.table.setItem(row, 5, i_est)


class RegistroPresupuestosTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.cargar_datos()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Filtros
        filtros_lay = QHBoxLayout()

        self.date_desde = QDateEdit()
        self.date_desde.setCalendarPopup(True)
        self.date_desde.setDate(QDate.currentDate().addDays(-30))

        self.date_hasta = QDateEdit()
        self.date_hasta.setCalendarPopup(True)
        self.date_hasta.setDate(QDate.currentDate())

        btn_filtrar = QPushButton("Filtrar")
        btn_filtrar.clicked.connect(self.cargar_datos)

        filtros_lay.addWidget(QLabel("Desde:"))
        filtros_lay.addWidget(self.date_desde)
        filtros_lay.addWidget(QLabel("Hasta:"))
        filtros_lay.addWidget(self.date_hasta)
        filtros_lay.addWidget(btn_filtrar)

        self.btn_export = QPushButton("Exportar")
        self.btn_export.clicked.connect(lambda: self._export(self.table))
        filtros_lay.addWidget(self.btn_export)

        filtros_lay.addStretch()

        layout.addLayout(filtros_lay)

        # Grilla
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Fecha", "Presupuesto", "Cliente", "Total", "Estado"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._abrir_detalle)

        layout.addWidget(self.table)

    def _export(self, tbl):
        from utils.export_utils import ExportUtils
        ExportUtils.exportar_tabla_csv(tbl, self, "Presupuestos")

    def _abrir_detalle(self, row, col):
        item_f = self.table.item(row, 0)
        if not item_f: return
        p_id = item_f.data(Qt.ItemDataRole.UserRole)
        if not p_id: return

        from ui.components.dialogs import DetalleVentaDialog
        # We reuse the dialog. We need to tweak DetalleVentaDialog slightly to handle Presupuesto details if we want it completely decoupled, but for now we'll just pass a flag or handle it internally. Wait, the prompt says: "Debe incluir la función de Doble Clic para abrir el DetalleVentaDialog (reutilizado) y ver los productos de ese presupuesto."
        dlg = DetalleVentaDialog(p_id, self, es_presupuesto=True)
        dlg.exec()

    def cargar_datos(self):
        d_desde = self.date_desde.date().toPyDate()
        d_hasta = self.date_hasta.date().toPyDate()

        from services.presupuesto_service import PresupuestoService
        presupuestos = PresupuestoService.obtener_por_fecha(d_desde, d_hasta)
        self.table.setRowCount(len(presupuestos))

        for row, p in enumerate(presupuestos):
            f_str = p.fecha.strftime("%Y-%m-%d %H:%M:%S")
            c_nom = p.cliente.nombre if p.cliente else "Consumidor Final"

            item_f = QTableWidgetItem(f_str)
            item_f.setData(Qt.ItemDataRole.UserRole, p.id)
            self.table.setItem(row, 0, item_f)
            self.table.setItem(row, 1, QTableWidgetItem(f"Presupuesto #{p.id}"))
            self.table.setItem(row, 2, QTableWidgetItem(c_nom))
            self.table.setItem(row, 3, QTableWidgetItem(f"${p.total:.2f}"))

            import datetime as dt
            estado_calc = p.estado
            # Dynamic calculation for expiration
            if estado_calc == "Pendiente":
                dias_transcurridos = (dt.datetime.utcnow() - p.fecha).days
                if dias_transcurridos > 15:
                    estado_calc = "Vencido"

            item_est = QTableWidgetItem(estado_calc)
            if estado_calc == "Pendiente":
                item_est.setForeground(Qt.GlobalColor.darkYellow)
            elif estado_calc == "Vencido":
                item_est.setForeground(Qt.GlobalColor.darkRed)
            elif estado_calc == "Cerrado":
                item_est.setForeground(Qt.GlobalColor.darkGreen)

            self.table.setItem(row, 4, item_est)


class CuentasCorrientesTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Panel Superior
        header_lay = QHBoxLayout()
        self.combo_clientes = QComboBox()
        self.combo_clientes.setEditable(True)
        self.combo_clientes.setPlaceholderText("Seleccionar Cliente...")

        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.combo_clientes.setCompleter(self.completer)

        self.btn_ver = QPushButton("Ver Estado de Cuenta")
        self.btn_ver.clicked.connect(self.cargar_datos)

        header_lay.addWidget(QLabel("Cliente:"))
        header_lay.addWidget(self.combo_clientes)
        header_lay.addWidget(self.btn_ver)
        header_lay.addStretch()

        layout.addLayout(header_lay)

        # Panel Resumen
        panel_resumen_lay = QHBoxLayout()
        self.lbl_saldo = QLabel("Saldo Total Adeudado: $0.00")
        self.lbl_saldo.setStyleSheet("font-size: 24px; font-weight: bold; color: red;")

        self.btn_exportar_pdf_cc = QPushButton("Exportar a PDF")
        self.btn_exportar_pdf_cc.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 10px;")
        self.btn_exportar_pdf_cc.clicked.connect(self._exportar_pdf)

        panel_resumen_lay.addWidget(self.lbl_saldo)
        panel_resumen_lay.addStretch()
        panel_resumen_lay.addWidget(self.btn_exportar_pdf_cc)

        layout.addLayout(panel_resumen_lay)

        # Grilla
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Fecha", "Concepto", "Debe", "Haber", "Saldo Histórico"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._abrir_detalle)
        layout.addWidget(self.table)

        self.cargar_clientes()

    def cargar_clientes(self):
        clientes = ClienteService.listar_todos()
        self.combo_clientes.clear()
        nombres = []
        for c in clientes:
            self.combo_clientes.addItem(c.nombre, c.id)
            nombres.append(c.nombre)
        self.completer.setModel(QStringListModel(nombres))

    def _abrir_detalle(self, row, col):
        item_f = self.table.item(row, 0)
        if not item_f: return
        venta_id = item_f.data(Qt.ItemDataRole.UserRole)
        if not venta_id: return

        from ui.components.dialogs import DetalleVentaDialog
        dlg = DetalleVentaDialog(venta_id, self)
        dlg.exec()

    def cargar_datos(self):
        c_id = self.combo_clientes.currentData()
        if not c_id:
            self.table.setRowCount(0)
            self.lbl_saldo.setText("Saldo Total Adeudado: $0.00")
            return

        movs = RegistrosService.obtener_estado_cc(c_id)
        self.table.setRowCount(len(movs))

        saldo_actual = 0.0
        for row, m in enumerate(movs):
            item_fecha = QTableWidgetItem(m['fecha'].strftime("%Y-%m-%d %H:%M:%S"))
            if 'venta_id' in m and m['venta_id']:
                item_fecha.setData(Qt.ItemDataRole.UserRole, m['venta_id'])

            self.table.setItem(row, 0, item_fecha)
            self.table.setItem(row, 1, QTableWidgetItem(m['concepto']))
            self.table.setItem(row, 2, QTableWidgetItem(f"${m['debe']:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"${m['haber']:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"${m['saldo']:.2f}"))
            saldo_actual = m['saldo']

        self.lbl_saldo.setText(f"Saldo Total Adeudado: ${saldo_actual:.2f}")
        if saldo_actual > 0:
            self.lbl_saldo.setStyleSheet("font-size: 24px; font-weight: bold; color: red;")
        else:
            self.lbl_saldo.setStyleSheet("font-size: 24px; font-weight: bold; color: green;")

    def _exportar_pdf(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from utils.export_utils import ExportUtils

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Guardar Reporte PDF", f"Reporte_{self.__class__.__name__}.pdf", "Archivos PDF (*.pdf)"
        )
        if filepath:
            try:
                ExportUtils.exportar_tabla_a_pdf(self.table, "Cuentas Corrientes - Reporte Oficial", filepath)
                QMessageBox.information(self, "Éxito", "El PDF se exportó correctamente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo exportar: {str(e)}")

        self.table.scrollToBottom()

class ContabilidadTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.cargar_datos()

    def _exportar_pdf_diario(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from utils.export_utils import ExportUtils
        filepath, _ = QFileDialog.getSaveFileName(self, "Guardar Reporte PDF", "Reporte_LibroDiario.pdf", "Archivos PDF (*.pdf)")
        if filepath:
            try:
                ExportUtils.exportar_tabla_a_pdf(self.tbl_diario, "Libro Diario - Reporte Oficial", filepath)
                QMessageBox.information(self, "Éxito", "El PDF se exportó correctamente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo exportar: {str(e)}")

    def _exportar_pdf_iva(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from utils.export_utils import ExportUtils
        filepath, _ = QFileDialog.getSaveFileName(self, "Guardar Reporte PDF", "Reporte_LibroIVA.pdf", "Archivos PDF (*.pdf)")
        if filepath:
            try:
                ExportUtils.exportar_tabla_a_pdf(self.tbl_iva, "Libro IVA - Reporte Oficial", filepath)
                QMessageBox.information(self, "Éxito", "El PDF se exportó correctamente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo exportar: {str(e)}")

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Filtros
        filtros_lay = QHBoxLayout()
        self.date_desde = QDateEdit()
        self.date_desde.setCalendarPopup(True)
        self.date_desde.setDate(QDate.currentDate().addDays(-30))

        self.date_hasta = QDateEdit()
        self.date_hasta.setCalendarPopup(True)
        self.date_hasta.setDate(QDate.currentDate())

        btn_filtrar = QPushButton("Filtrar Registros")
        btn_filtrar.clicked.connect(self.cargar_datos)

        filtros_lay.addWidget(QLabel("Desde:"))
        filtros_lay.addWidget(self.date_desde)
        filtros_lay.addWidget(QLabel("Hasta:"))
        filtros_lay.addWidget(self.date_hasta)
        filtros_lay.addWidget(btn_filtrar)
        filtros_lay.addStretch()
        layout.addLayout(filtros_lay)

        # Splitter para las dos grillas
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Widget Libro Diario
        w_diario = QWidget()
        lay_diario = QVBoxLayout(w_diario)
        lay_diario.setContentsMargins(0,0,0,0)
        lbl_diario = QLabel("Libro Diario (Asientos Generados)")
        lbl_diario.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.tbl_diario = QTableWidget(0, 5)
        self.tbl_diario.setHorizontalHeaderLabels(["ID", "Fecha", "Cuenta", "Debe", "Haber"])
        self.tbl_diario.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_diario.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.btn_exportar_pdf_diario = QPushButton("Exportar a PDF")
        self.btn_exportar_pdf_diario.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 10px;")
        self.btn_exportar_pdf_diario.clicked.connect(self._exportar_pdf_diario)

        lay_diario.addWidget(lbl_diario)
        lay_diario.addWidget(self.btn_exportar_pdf_diario)
        lay_diario.addWidget(self.tbl_diario)

        # Widget Libro IVA
        w_iva = QWidget()
        lay_iva = QVBoxLayout(w_iva)
        lay_iva.setContentsMargins(0,0,0,0)

        # Panel Totales IVA
        self.panel_iva = QHBoxLayout()
        self.lbl_iva_ventas = QLabel("Total IVA Débito (Ventas): $0.00")
        self.lbl_iva_ventas.setStyleSheet("font-size: 16px; font-weight: bold; color: #c0392b; background: #fadbd8; padding: 10px; border-radius: 5px;")
        self.lbl_iva_compras = QLabel("Total IVA Crédito (Compras): $0.00")
        self.lbl_iva_compras.setStyleSheet("font-size: 16px; font-weight: bold; color: #27ae60; background: #d5f5e3; padding: 10px; border-radius: 5px;")
        self.lbl_iva_saldo = QLabel("Saldo IVA: $0.00")
        self.lbl_iva_saldo.setStyleSheet("font-size: 18px; font-weight: bold; color: #2980b9; background: #d6eaf8; padding: 10px; border-radius: 5px;")
        self.panel_iva.addWidget(self.lbl_iva_ventas)
        self.panel_iva.addWidget(self.lbl_iva_compras)
        self.panel_iva.addWidget(self.lbl_iva_saldo)

        self.tbl_iva = QTableWidget(0, 6)
        self.tbl_iva.setHorizontalHeaderLabels(["Fecha", "Tipo (Compra/Venta)", "Comprobante", "Neto Gravado", "IVA", "Total"])
        self.tbl_iva.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_iva.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.btn_exportar_pdf_iva = QPushButton("Exportar a PDF")
        self.btn_exportar_pdf_iva.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 10px;")
        self.btn_exportar_pdf_iva.clicked.connect(self._exportar_pdf_iva)

        lay_iva.addLayout(self.panel_iva)
        lay_iva.addWidget(self.btn_exportar_pdf_iva)
        lay_iva.addWidget(self.tbl_iva)

        splitter.addWidget(w_diario)
        splitter.addWidget(w_iva)

        layout.addWidget(splitter)

    def cargar_datos(self):
        d_desde = self.date_desde.date().toPyDate()
        d_hasta = self.date_hasta.date().toPyDate()

        # Cargar Diario
        asientos = RegistrosService.obtener_asientos_diarios(d_desde, d_hasta)
        self.tbl_diario.setRowCount(len(asientos))
        for row, a in enumerate(asientos):
            self.tbl_diario.setItem(row, 0, QTableWidgetItem(str(a.id)))
            self.tbl_diario.setItem(row, 1, QTableWidgetItem(a.fecha.strftime("%Y-%m-%d")))
            self.tbl_diario.setItem(row, 2, QTableWidgetItem(f"{a.cuenta} ({a.descripcion})"))
            self.tbl_diario.setItem(row, 3, QTableWidgetItem(f"${a.debe:.2f}"))
            self.tbl_diario.setItem(row, 4, QTableWidgetItem(f"${a.haber:.2f}"))

        # Cargar Libro IVA y calcular totales
        registros_iva = RegistrosService.obtener_libro_iva(d_desde, d_hasta)
        self.tbl_iva.setRowCount(len(registros_iva))

        total_debito = 0.0
        total_credito = 0.0

        for row, r in enumerate(registros_iva):
            self.tbl_iva.setItem(row, 0, QTableWidgetItem(r.fecha.strftime("%Y-%m-%d")))
            self.tbl_iva.setItem(row, 1, QTableWidgetItem(r.tipo))
            self.tbl_iva.setItem(row, 2, QTableWidgetItem(r.comprobante))
            self.tbl_iva.setItem(row, 3, QTableWidgetItem(f"${r.neto_gravado:.2f}"))
            self.tbl_iva.setItem(row, 4, QTableWidgetItem(f"${r.iva_21:.2f}"))
            self.tbl_iva.setItem(row, 5, QTableWidgetItem(f"${r.total:.2f}"))

            if r.tipo == "Venta":
                total_debito += r.iva_21
            elif r.tipo == "Compra":
                total_credito += r.iva_21

        saldo = total_debito - total_credito

        if hasattr(self, 'lbl_iva_ventas'):
            self.lbl_iva_ventas.setText(f"Total IVA Débito (Ventas): ${total_debito:.2f}")
            self.lbl_iva_compras.setText(f"Total IVA Crédito (Compras): ${total_credito:.2f}")
            self.lbl_iva_saldo.setText(f"Saldo IVA: ${saldo:.2f}")
            if saldo > 0:
                self.lbl_iva_saldo.setStyleSheet("font-size: 18px; font-weight: bold; color: #c0392b; background: #fadbd8; padding: 10px; border-radius: 5px;")
            else:
                self.lbl_iva_saldo.setStyleSheet("font-size: 18px; font-weight: bold; color: #27ae60; background: #d5f5e3; padding: 10px; border-radius: 5px;")



class LiquidezBancosTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.cargar_datos()

    def _exportar_pdf_liquidez(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from utils.export_utils import ExportUtils
        filepath, _ = QFileDialog.getSaveFileName(self, "Guardar Reporte PDF", "Reporte_Liquidez.pdf", "Archivos PDF (*.pdf)")
        if filepath:
            try:
                ExportUtils.exportar_tabla_a_pdf(self.table, "Liquidez y Bancos - Reporte Oficial", filepath)
                QMessageBox.information(self, "Éxito", "El PDF se exportó correctamente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo exportar: {str(e)}")

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Panel Superior (Resumen de Liquidez)
        panel_resumen = QWidget()
        resumen_lay = QHBoxLayout(panel_resumen)

        self.lbl_efectivo = QLabel("Caja Fuerte (Efectivo):\n$ 0.00")
        self.lbl_efectivo.setStyleSheet("font-size: 12px; font-weight: bold; color: #27ae60; background: #eaeee8; padding: 8px; border-radius: 5px;")
        self.lbl_efectivo.setWordWrap(True)
        self.lbl_efectivo.setWordWrap(True)
        self.lbl_efectivo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_bancos = QLabel("Cuentas Bancarias:\n$ 0.00")
        self.lbl_bancos.setStyleSheet("font-size: 12px; font-weight: bold; color: #2980b9; background: #eaf2f8; padding: 8px; border-radius: 5px;")
        self.lbl_bancos.setWordWrap(True)
        self.lbl_bancos.setWordWrap(True)
        self.lbl_bancos.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_cheques = QLabel("Cheques en Cartera (Físico):\n$ 0.00")
        self.lbl_cheques.setStyleSheet("font-size: 12px; font-weight: bold; color: #8e44ad; background: #f5eef8; padding: 8px; border-radius: 5px;")
        self.lbl_cheques.setWordWrap(True)
        self.lbl_cheques.setWordWrap(True)
        self.lbl_cheques.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_tarjetas = QLabel("Acreditaciones Pendientes (Tarjetas):\n$ 0.00")
        self.lbl_tarjetas.setStyleSheet("font-size: 12px; font-weight: bold; color: #f39c12; background: #fef5e7; padding: 8px; border-radius: 5px;")
        self.lbl_tarjetas.setWordWrap(True)
        self.lbl_tarjetas.setWordWrap(True)
        self.lbl_tarjetas.setAlignment(Qt.AlignmentFlag.AlignCenter)

        resumen_lay.addWidget(self.lbl_efectivo)
        resumen_lay.addWidget(self.lbl_bancos)
        resumen_lay.addWidget(self.lbl_cheques)
        resumen_lay.addWidget(self.lbl_tarjetas)

        layout.addWidget(panel_resumen)

        # Grilla de Acreditaciones Próximas
        lbl_grilla = QLabel("Próximas Acreditaciones (Tarjetas y Cheques)")
        lbl_grilla.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 20px;")

        self.btn_exportar_pdf_liquidez = QPushButton("Exportar a PDF")
        self.btn_exportar_pdf_liquidez.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 10px;")
        self.btn_exportar_pdf_liquidez.clicked.connect(self._exportar_pdf_liquidez)

        box_grilla = QHBoxLayout()
        box_grilla.addWidget(lbl_grilla)
        box_grilla.addStretch()
        box_grilla.addWidget(self.btn_exportar_pdf_liquidez)

        layout.addLayout(box_grilla)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Fecha Acreditación/Venc.", "Origen (Banco/Tarjeta)", "Cuotas/Tipo", "Monto Neto a Ingresar", "Estado"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.table)

        btn_refresh = QPushButton("Actualizar Liquidez")
        btn_refresh.clicked.connect(self.cargar_datos)
        layout.addWidget(btn_refresh)

    def cargar_datos(self):
        # 1. Resumen de Liquidez (Fetch for Box & Banks)
        liquidez = RegistrosService.obtener_liquidez_actual()
        self.lbl_efectivo.setText(f"Caja Fuerte (Efectivo):\n$ {liquidez.get('efectivo', 0):.2f}")
        self.lbl_bancos.setText(f"Cuentas Bancarias:\n$ {liquidez.get('bancos', 0):.2f}")

        # 2. Grilla (Fetch details)
        self.table.setRowCount(0)
        pendientes = RegistrosService.obtener_proximas_acreditaciones()

        total_cheques = 0.0
        total_tarjetas = 0.0

        hoy = dt.date.today()
        from PyQt6.QtGui import QBrush, QColor, QFont

        for row, p in enumerate(pendientes):
            self.table.insertRow(row)
            fecha_acred = p.get('fecha')
            f_str = fecha_acred.strftime("%Y-%m-%d") if fecha_acred else ""

            i_fec = QTableWidgetItem(f_str)
            if fecha_acred and fecha_acred <= hoy:
                i_fec.setForeground(Qt.GlobalColor.red)
                i_fec.setToolTip("Debería estar acreditado hoy o está atrasado.")

            self.table.setItem(row, 0, i_fec)

            origen = str(p.get('origen', ''))
            self.table.setItem(row, 1, QTableWidgetItem(origen))
            self.table.setItem(row, 2, QTableWidgetItem(str(p.get('tipo', ''))))

            monto = float(p.get('monto_neto', 0.0))
            i_monto = QTableWidgetItem(f"${monto:.2f}")
            i_monto.setForeground(Qt.GlobalColor.darkGreen)
            fnt = QFont()
            fnt.setBold(True)
            i_monto.setFont(fnt)
            self.table.setItem(row, 3, i_monto)

            self.table.setItem(row, 4, QTableWidgetItem(str(p.get('estado', ''))))

            # Sumarización segura basada en el origen
            if "[FÍSICO]" in origen.upper() or "CHEQUE" in origen.upper():
                total_cheques += monto
            elif "[BANCARIO]" in origen.upper() or "TARJETA" in origen.upper():
                total_tarjetas += monto

        self.lbl_cheques.setText(f"Cheques en Cartera (Físico):\n$ {total_cheques:.2f}")
        self.lbl_tarjetas.setText(f"Acreditaciones Pendientes (Tarjetas):\n$ {total_tarjetas:.2f}")


class RegistrosView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.tab_ventas = RegistroVentasTab()
        self.tab_pres = RegistroPresupuestosTab()
        self.tab_cc = CuentasCorrientesTab()
        self.tab_conta = ContabilidadTab()
        self.tab_liquidez = LiquidezBancosTab()

        self.tabs.addTab(self.tab_ventas, "Registro de Ventas")
        self.tabs.addTab(self.tab_pres, "Presupuestos")
        self.tabs.addTab(self.tab_cc, "Cuentas Corrientes (Clientes)")
        self.tabs.addTab(self.tab_conta, "Libro Diario e IVA")
        self.tabs.addTab(self.tab_liquidez, "Liquidez y Bancos")

        layout.addWidget(self.tabs)

    def showEvent(self, event):
        super().showEvent(event)
        self.tab_ventas.cargar_datos()
        self.tab_pres.cargar_datos()
        self.tab_cc.cargar_clientes()
        self.tab_conta.cargar_datos()
        self.tab_liquidez.cargar_datos()
