from PyQt6.QtWidgets import (
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
        filtros_lay.addStretch()

        layout.addLayout(filtros_lay)

        # Grilla
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Fecha", "Comprobante", "Cliente", "Total", "Método Pago"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.table)

    def cargar_datos(self):
        d_desde = self.date_desde.date().toPyDate()
        d_hasta = self.date_hasta.date().toPyDate()
        comp = self.combo_comprobante.currentText()

        ventas = RegistrosService.obtener_ventas(d_desde, d_hasta, comp)
        self.table.setRowCount(len(ventas))

        for row, v in enumerate(ventas):
            f_str = v.fecha.strftime("%Y-%m-%d %H:%M:%S")
            c_nom = v.cliente.nombre if v.cliente else "Consumidor Final"

            self.table.setItem(row, 0, QTableWidgetItem(f_str))
            self.table.setItem(row, 1, QTableWidgetItem(f"{v.tipo_comprobante} #{v.id}"))
            self.table.setItem(row, 2, QTableWidgetItem(c_nom))
            self.table.setItem(row, 3, QTableWidgetItem(f"${v.total:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(v.metodo_pago))

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
        self.lbl_saldo = QLabel("Saldo Total Adeudado: $0.00")
        self.lbl_saldo.setStyleSheet("font-size: 24px; font-weight: bold; color: red;")
        layout.addWidget(self.lbl_saldo)

        # Grilla
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Fecha", "Concepto", "Debe", "Haber", "Saldo Histórico"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
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
            self.table.setItem(row, 0, QTableWidgetItem(m.fecha.strftime("%Y-%m-%d %H:%M:%S")))
            self.table.setItem(row, 1, QTableWidgetItem(m.concepto))
            self.table.setItem(row, 2, QTableWidgetItem(f"${m.debe:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"${m.haber:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"${m.saldo:.2f}"))
            saldo_actual = m.saldo

        self.lbl_saldo.setText(f"Saldo Total Adeudado: ${saldo_actual:.2f}")
        if saldo_actual > 0:
            self.lbl_saldo.setStyleSheet("font-size: 24px; font-weight: bold; color: red;")
        else:
            self.lbl_saldo.setStyleSheet("font-size: 24px; font-weight: bold; color: green;")

        self.table.scrollToBottom()

class ContabilidadTab(QWidget):
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

        lay_diario.addWidget(lbl_diario)
        lay_diario.addWidget(self.tbl_diario)

        # Widget Libro IVA
        w_iva = QWidget()
        lay_iva = QVBoxLayout(w_iva)
        lay_iva.setContentsMargins(0,0,0,0)
        lbl_iva = QLabel("Libro IVA (Débito Fiscal)")
        lbl_iva.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.tbl_iva = QTableWidget(0, 6)
        self.tbl_iva.setHorizontalHeaderLabels(["Fecha", "Comprobante", "Número", "Neto Gravado", "IVA Facturado", "Total"])
        self.tbl_iva.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_iva.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        lay_iva.addWidget(lbl_iva)
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

        # Cargar IVA
        registros_iva = RegistrosService.obtener_libro_iva(d_desde, d_hasta)
        self.tbl_iva.setRowCount(len(registros_iva))
        for row, r in enumerate(registros_iva):
            self.tbl_iva.setItem(row, 0, QTableWidgetItem(r.fecha.strftime("%Y-%m-%d")))
            self.tbl_iva.setItem(row, 1, QTableWidgetItem(r.tipo_comprobante))
            self.tbl_iva.setItem(row, 2, QTableWidgetItem(r.numero_comprobante))
            self.tbl_iva.setItem(row, 3, QTableWidgetItem(f"${r.neto_gravado:.2f}"))
            self.tbl_iva.setItem(row, 4, QTableWidgetItem(f"${r.iva_facturado:.2f}"))
            self.tbl_iva.setItem(row, 5, QTableWidgetItem(f"${r.total:.2f}"))


class RegistrosView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.tab_ventas = RegistroVentasTab()
        self.tab_cc = CuentasCorrientesTab()
        self.tab_conta = ContabilidadTab()

        self.tabs.addTab(self.tab_ventas, "Registro de Ventas")
        self.tabs.addTab(self.tab_cc, "Cuentas Corrientes (Clientes)")
        self.tabs.addTab(self.tab_conta, "Libro Diario e IVA")

        layout.addWidget(self.tabs)

    def showEvent(self, event):
        super().showEvent(event)
        self.tab_ventas.cargar_datos()
        self.tab_cc.cargar_clientes()
        self.tab_conta.cargar_datos()
