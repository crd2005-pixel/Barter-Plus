# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QPushButton, QHBoxLayout
)
from PyQt5.QtCore import Qt
from db import SessionLocal, Venta, VentaPago
try:
    from db.models.gastos import Gasto
except ImportError:
    Gasto = None
from db.models.clientes import CuentaCorrienteCliente

class DetalleCajaDialog(QDialog):
    def __init__(self, cierre, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Detalle de Caja - {cierre.fecha_desde} a {cierre.fecha_hasta}")
        self.resize(900, 600)
        self.cierre = cierre

        layout = QVBoxLayout(self)

        # Info header
        lbl_info = QLabel(f"<b>Cierre ID:</b> {cierre.id} | <b>Estado:</b> {cierre.estado}<br>"
                          f"<b>Desde:</b> {cierre.fecha_desde} <b>Hasta:</b> {cierre.fecha_hasta}")
        layout.addWidget(lbl_info)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Tabs content
        self.tab_ventas = self._create_table(["ID", "Fecha", "Cliente", "Total", "Pagos"])
        self.tab_gastos = self._create_table(["ID", "Fecha", "Categoría", "Monto", "Medio", "Nota"])
        self.tab_ctacte = self._create_table(["ID", "Fecha", "Cliente", "Monto", "Concepto"])

        self.tabs.addTab(self.tab_ventas, "Ventas")
        self.tabs.addTab(self.tab_gastos, "Gastos")
        self.tabs.addTab(self.tab_ctacte, "Mov. Cta Cte")

        # Close button
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(btn_close)
        layout.addLayout(hlayout)

        self._load_data()

    def _create_table(self, headers):
        tbl = QTableWidget(0, len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        return tbl

    def _load_data(self):
        start = self.cierre.fecha_desde
        end = self.cierre.fecha_hasta

        with SessionLocal() as s:
            # 1. Ventas
            ventas = s.query(Venta).filter(Venta.fecha >= start, Venta.fecha <= end).all()
            self.tab_ventas.setRowCount(len(ventas))
            for r, v in enumerate(ventas):
                # Obtener detalles de pagos si existen
                pagos_str = v.forma_pago
                try:
                    if VentaPago:
                        pags = s.query(VentaPago).filter_by(venta_id=v.id).all()
                        if pags:
                            pagos_str = ", ".join([f"{p.medio}: {p.monto}" for p in pags])
                except Exception:
                    pass

                cli_nom = v.cliente.nombre if v.cliente else "Consumidor Final"

                self.tab_ventas.setItem(r, 0, QTableWidgetItem(str(v.id)))
                self.tab_ventas.setItem(r, 1, QTableWidgetItem(str(v.fecha)))
                self.tab_ventas.setItem(r, 2, QTableWidgetItem(cli_nom))
                self.tab_ventas.setItem(r, 3, QTableWidgetItem(f"{v.total:.2f}"))
                self.tab_ventas.setItem(r, 4, QTableWidgetItem(pagos_str))

            # 2. Gastos
            if Gasto:
                gastos = s.query(Gasto).filter(Gasto.fecha >= start, Gasto.fecha <= end).all()
                self.tab_gastos.setRowCount(len(gastos))
                for r, g in enumerate(gastos):
                    cat_nom = g.categoria.nombre if g.categoria else ""
                    self.tab_gastos.setItem(r, 0, QTableWidgetItem(str(g.id)))
                    self.tab_gastos.setItem(r, 1, QTableWidgetItem(str(g.fecha)))
                    self.tab_gastos.setItem(r, 2, QTableWidgetItem(cat_nom))
                    self.tab_gastos.setItem(r, 3, QTableWidgetItem(f"{g.monto:.2f}"))
                    self.tab_gastos.setItem(r, 4, QTableWidgetItem(g.medio))
                    self.tab_gastos.setItem(r, 5, QTableWidgetItem(g.notas or ""))

            # 3. Cta Cte (cobros son negativos, pero mostramos todos los movs del periodo)
            # Solo nos interesan los que afectan la caja (pagos del cliente -> monto < 0 en la cuenta del cliente)
            # Ojo: la logica de caja usa monto < 0 como ingreso de dinero (cobro)
            ctas = s.query(CuentaCorrienteCliente).filter(
                CuentaCorrienteCliente.fecha >= start,
                CuentaCorrienteCliente.fecha <= end,
                CuentaCorrienteCliente.monto < 0 # Solo ingresos de dinero (cobros)
            ).all()
            self.tab_ctacte.setRowCount(len(ctas))
            for r, c in enumerate(ctas):
                cli_nom = c.cliente.nombre if c.cliente else "?"
                self.tab_ctacte.setItem(r, 0, QTableWidgetItem(str(c.id)))
                self.tab_ctacte.setItem(r, 1, QTableWidgetItem(str(c.fecha)))
                self.tab_ctacte.setItem(r, 2, QTableWidgetItem(cli_nom))
                self.tab_ctacte.setItem(r, 3, QTableWidgetItem(f"{abs(c.monto):.2f}"))
                self.tab_ctacte.setItem(r, 4, QTableWidgetItem(c.concepto or ""))
