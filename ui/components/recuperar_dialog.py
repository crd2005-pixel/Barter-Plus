from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
                             QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QMessageBox)
from PyQt6.QtCore import Qt
from services.presupuesto_service import PresupuestoService
from services.venta_service import VentaService

class RecuperarComprobanteDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cargar Comprobante")
        self.resize(700, 500)
        self.detalles_recuperados = [] # Aquí dejaremos los items
        self.cliente_id_seleccionado = None
        self.presupuesto_origen_id = None
        self.setup_ui()
        self.cargar_datos()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()

        # Tab Presupuestos
        self.tab_pres = QWidget()
        lay_pres = QVBoxLayout(self.tab_pres)
        self.tbl_pres = QTableWidget(0, 4)
        self.tbl_pres.setHorizontalHeaderLabels(["ID", "Fecha", "Cliente", "Total"])
        self.tbl_pres.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_pres.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_pres.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_pres.cellDoubleClicked.connect(self.cargar_seleccion)
        lay_pres.addWidget(self.tbl_pres)
        self.tabs.addTab(self.tab_pres, "Presupuestos")

        # Tab Remitos
        self.tab_remitos = QWidget()
        lay_rem = QVBoxLayout(self.tab_remitos)
        self.tbl_rem = QTableWidget(0, 4)
        self.tbl_rem.setHorizontalHeaderLabels(["ID", "Fecha", "Cliente", "Total"])
        self.tbl_rem.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_rem.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_rem.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_rem.cellDoubleClicked.connect(self.cargar_seleccion)
        lay_rem.addWidget(self.tbl_rem)
        self.tabs.addTab(self.tab_remitos, "Remitos (Últimos)")

        layout.addWidget(self.tabs)

        # Botonera
        h_btn = QHBoxLayout()
        btn_cargar = QPushButton("Cargar Comprobante al POS")
        btn_cargar.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; height: 35px;")
        btn_cargar.clicked.connect(self.cargar_seleccion)
        h_btn.addStretch()
        h_btn.addWidget(btn_cargar)
        layout.addLayout(h_btn)

    def cargar_datos(self):
        # Cargar Presupuestos
        presupuestos = PresupuestoService.obtener_pendientes_activos(15)
        self.tbl_pres.setRowCount(len(presupuestos))
        for r, p in enumerate(presupuestos):
            self.tbl_pres.setItem(r, 0, QTableWidgetItem(str(p['id'])))
            self.tbl_pres.setItem(r, 1, QTableWidgetItem(p['fecha'].strftime("%Y-%m-%d %H:%M")))
            c_nom = p.get('cliente_nombre') or (f"Cliente ID: {p['cliente_id']}" if p.get('cliente_id') else "Genérico")
            item_cliente = QTableWidgetItem(c_nom)
            if p['cliente_id']: item_cliente.setData(Qt.ItemDataRole.UserRole, p['cliente_id'])
            self.tbl_pres.setItem(r, 2, item_cliente)
            self.tbl_pres.setItem(r, 3, QTableWidgetItem(f"${p['total']:.2f}"))

        # Cargar Remitos (Podemos reusar un query de ventas)
        import datetime as dt
        from services.registros_service import RegistrosService
        d_hasta = dt.date.today()
        d_desde = d_hasta - dt.timedelta(days=15)
        ventas = RegistrosService.obtener_ventas(d_desde, d_hasta, comprobante="Remito")

        self.tbl_rem.setRowCount(len(ventas))
        for r, v in enumerate(ventas):
            self.tbl_rem.setItem(r, 0, QTableWidgetItem(str(v.id)))
            self.tbl_rem.setItem(r, 1, QTableWidgetItem(v.fecha.strftime("%Y-%m-%d %H:%M")))
            c_nom = v.cliente.nombre if v.cliente else "Consumidor Final"
            item_cliente = QTableWidgetItem(c_nom)
            if v.cliente_id: item_cliente.setData(Qt.ItemDataRole.UserRole, v.cliente_id)
            self.tbl_rem.setItem(r, 2, item_cliente)
            self.tbl_rem.setItem(r, 3, QTableWidgetItem(f"${v.total:.2f}"))

    def cargar_seleccion(self):
        curr_tab = self.tabs.currentIndex()
        if curr_tab == 0:
            row = self.tbl_pres.currentRow()
            if row < 0: return
            p_id = int(self.tbl_pres.item(row, 0).text())

            item_cliente = self.tbl_pres.item(row, 2)
            if item_cliente: self.cliente_id_seleccionado = item_cliente.data(Qt.ItemDataRole.UserRole)

            self.presupuesto_origen_id = p_id
            self.detalles_recuperados = PresupuestoService.obtener_detalle(p_id)
            self.accept()
        else:
            row = self.tbl_rem.currentRow()
            if row < 0: return
            v_id = int(self.tbl_rem.item(row, 0).text())

            item_cliente = self.tbl_rem.item(row, 2)
            if item_cliente: self.cliente_id_seleccionado = item_cliente.data(Qt.ItemDataRole.UserRole)

            # Rehydrate from DetalleVenta
            from database.conexion import get_session
            from database.models.venta import DetalleVenta
            from sqlalchemy.orm import joinedload
            with get_session() as session:
                detalles = session.query(DetalleVenta).options(joinedload(DetalleVenta.producto)).filter(DetalleVenta.venta_id == v_id).all()
                self.detalles_recuperados = [{
                    "id": d.producto_id,
                    "codigo": d.codigo_barras or "",
                    "marca": d.producto.marca.nombre if (d.producto and d.producto.marca) else "",
                    "nombre": d.descripcion,
                    "cantidad": d.cantidad,
                    "precio_base": d.precio_unitario,
                    "descuento_unit": d.descuento_unitario,
                    "subtotal": d.subtotal
                } for d in detalles]
            self.accept()
