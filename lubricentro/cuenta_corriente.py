# -*- coding: utf-8 -*-
# cuenta_corriente.py (1.6.2 parche)
# Modelo: CuentaCorrienteCliente tiene SOLO 'monto' (+debe / -haber).

import datetime as dt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox
)
from PyQt5.QtCore import Qt

from db import SessionLocal, Cliente, CuentaCorrienteCliente

class CuentaCorrienteTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        # Buscar cliente
        hl = QHBoxLayout()
        hl.addWidget(QLabel("Cliente o DNI:"))
        self.inp_cliente = QLineEdit(self); hl.addWidget(self.inp_cliente)
        btn_buscar = QPushButton("Buscar", self); btn_buscar.clicked.connect(self.buscar_cliente)
        hl.addWidget(btn_buscar)
        layout.addLayout(hl)

        # Tabla
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Concepto", "Débito", "Crédito", "Saldo"])
        layout.addWidget(self.tbl)

        # Alta
        hl2 = QHBoxLayout()
        self.inp_concepto = QLineEdit(); self.inp_concepto.setPlaceholderText("Concepto")
        self.inp_debito   = QLineEdit(); self.inp_debito.setPlaceholderText("Débito")
        self.inp_credito  = QLineEdit(); self.inp_credito.setPlaceholderText("Crédito")
        btn_add = QPushButton("Agregar Movimiento"); btn_add.clicked.connect(self.add_mov)
        for w in (QLabel("Concepto:"), self.inp_concepto, QLabel("Débito:"), self.inp_debito,
                  QLabel("Crédito:"), self.inp_credito, btn_add):
            hl2.addWidget(w)
        layout.addLayout(hl2)

        self.current_cliente = None

    # Helpers
    def _find_cliente(self, term: str):
        term = term.strip()
        if not term: return None
        with SessionLocal() as s:
            q = s.query(Cliente)
            if term.isdigit():
                cli = q.filter(Cliente.cuit_dni == term).first()
                if cli: return cli
            return q.filter(Cliente.nombre.ilike(f"%{term}%")).first()

    def _rows(self, cliente_id: int):
        with SessionLocal() as s:
            movs = (
                s.query(CuentaCorrienteCliente)
                .filter(CuentaCorrienteCliente.cliente_id == cliente_id)
                .order_by(CuentaCorrienteCliente.fecha.asc(), CuentaCorrienteCliente.id.asc())
                .all()
            )
        saldo = 0.0; rows = []
        for m in movs:
            monto = float(m.monto or 0.0)
            deb = monto if monto > 0 else 0.0
            hab = -monto if monto < 0 else 0.0
            saldo += monto
            fecha = m.fecha.strftime("%Y-%m-%d %H:%M") if isinstance(m.fecha, dt.datetime) else str(m.fecha or "")
            rows.append((fecha, m.concepto or "", deb, hab, saldo))
        return rows

    def _set(self, r, c, v):
        it = QTableWidgetItem("" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v)))
        it.setFlags(it.flags() ^ Qt.ItemIsEditable); self.tbl.setItem(r, c, it)

    # UI actions
    def buscar_cliente(self):
        term = self.inp_cliente.text().strip()
        if not term:
            QMessageBox.warning(self, "Cuentas Corrientes", "Ingrese nombre o DNI.")
            return
        cli = self._find_cliente(term)
        if not cli:
            QMessageBox.information(self, "Cuentas Corrientes", "Cliente no encontrado.")
            self.current_cliente = None; self.tbl.setRowCount(0); return
        self.current_cliente = cli
        self.reload()

    def reload(self):
        if not self.current_cliente:
            self.tbl.setRowCount(0); return
        rows = self._rows(self.current_cliente.id)
        self.tbl.setRowCount(len(rows))
        for r, (f, cpto, d, h, sld) in enumerate(rows):
            self._set(r, 0, f); self._set(r, 1, cpto); self._set(r, 2, d); self._set(r, 3, h); self._set(r, 4, sld)

    def add_mov(self):
        if not self.current_cliente:
            QMessageBox.warning(self, "Cuentas Corrientes", "Seleccione un cliente primero.")
            return
        cpto = self.inp_concepto.text().strip()
        try:
            deb = float(self.inp_debito.text() or 0)
            hab = float(self.inp_credito.text() or 0)
        except ValueError:
            QMessageBox.warning(self, "Cuentas Corrientes", "Débito/Crédito deben ser numéricos.")
            return
        monto = deb - hab
        if monto == 0 and not cpto:
            QMessageBox.warning(self, "Cuentas Corrientes", "Complete concepto o importe.")
            return
        with SessionLocal() as s:
            mov = CuentaCorrienteCliente(
                cliente_id=self.current_cliente.id,
                fecha=dt.datetime.utcnow(),
                concepto=cpto,
                monto=monto
            )
            s.add(mov); s.commit()
        QMessageBox.information(self, "Cuentas Corrientes", "Movimiento agregado.")
        self.inp_concepto.clear(); self.inp_debito.clear(); self.inp_credito.clear()
        self.reload()
