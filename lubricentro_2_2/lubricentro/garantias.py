# garantias.py
# ===========================
# Módulo de gestión de Garantías
# ===========================

import datetime as dt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox,
    QMessageBox, QFormLayout, QTabWidget
)
from PyQt5.QtCore import QDate

from db import SessionLocal, Garantia, ReclamoGarantia, Cliente, Producto


# --------------------------
# Subpestaña 1: Garantías vigentes
# --------------------------
class GarantiasVigentesTab(QWidget):
    def __init__(self):
        super().__init__()
        self.session = SessionLocal()

        layout = QVBoxLayout(self)

        # Filtro
        fl = QHBoxLayout()
        self.inp_buscar = QLineEdit()
        self.inp_buscar.setPlaceholderText("Buscar cliente o producto...")
        btn_buscar = QPushButton("Buscar")
        btn_buscar.clicked.connect(self.reload)
        fl.addWidget(QLabel("Filtro:"))
        fl.addWidget(self.inp_buscar)
        fl.addWidget(btn_buscar)
        layout.addLayout(fl)

        # Tabla
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels([
            "ID", "Cliente", "Producto", "Fecha compra",
            "Vence", "Estado"
        ])
        layout.addWidget(self.tbl)

        self.reload()

    def reload(self):
        self.tbl.setRowCount(0)
        filtro = self.inp_buscar.text().strip()

        q = self.session.query(Garantia).join(Cliente).join(Producto)
        if filtro:
            q = q.filter(
                (Cliente.nombre.ilike(f"%{filtro}%")) |
                (Producto.nombre.ilike(f"%{filtro}%"))
            )
        rows = q.order_by(Garantia.fecha_compra.desc()).limit(500).all()

        hoy = dt.datetime.utcnow().date()
        for g in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(str(g.id)))
            self.tbl.setItem(r, 1, QTableWidgetItem(g.cliente.nombre if g.cliente else ""))
            self.tbl.setItem(r, 2, QTableWidgetItem(g.producto.nombre if g.producto else ""))
            self.tbl.setItem(r, 3, QTableWidgetItem(g.fecha_compra.strftime("%d/%m/%Y")))
            vence = g.fecha_vencimiento.date() if g.fecha_vencimiento else None
            self.tbl.setItem(r, 4, QTableWidgetItem(vence.strftime("%d/%m/%Y") if vence else "-"))

            estado = "Vigente"
            if vence and vence < hoy:
                estado = "Vencida"
            self.tbl.setItem(r, 5, QTableWidgetItem(estado))


# --------------------------
# Subpestaña 2: Reclamos de garantía
# --------------------------
class ReclamosGarantiaTab(QWidget):
    def __init__(self):
        super().__init__()
        self.session = SessionLocal()

        layout = QVBoxLayout(self)

        # Formulario de alta
        form = QFormLayout()
        self.inp_idgar = QLineEdit()
        self.inp_obs = QLineEdit()
        self.cbo_estado = QComboBox()
        self.cbo_estado.addItems([
            "Ingresado",
            "Enviado a servicio técnico",
            "En reparación",
            "Reparado",
            "Reemplazado",
            "Devuelto al cliente"
        ])
        btn_add = QPushButton("Registrar / Actualizar")
        btn_add.clicked.connect(self.add_reclamo)
        form.addRow("ID Garantía:", self.inp_idgar)
        form.addRow("Observaciones:", self.inp_obs)
        form.addRow("Estado:", self.cbo_estado)
        form.addRow(btn_add)
        layout.addLayout(form)

        # Tabla
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels([
            "ID", "Garantía", "Fecha ingreso", "Estado", "Observaciones"
        ])
        layout.addWidget(self.tbl)

        self.reload()

    def add_reclamo(self):
        gid = self.inp_idgar.text().strip()
        if not gid.isdigit():
            QMessageBox.warning(self, "Dato inválido", "Ingrese un ID de garantía válido")
            return
        g = self.session.get(Garantia, int(gid))
        if not g:
            QMessageBox.warning(self, "Garantía", "No existe garantía con ese ID")
            return

        rec = ReclamoGarantia(
            garantia_id=g.id,
            fecha_ingreso=dt.datetime.utcnow(),
            estado=self.cbo_estado.currentText(),
            observaciones=self.inp_obs.text().strip()
        )
        self.session.add(rec)
        self.session.commit()
        QMessageBox.information(self, "OK", "Reclamo registrado")
        self.inp_idgar.clear()
        self.inp_obs.clear()
        self.reload()

    def reload(self):
        self.tbl.setRowCount(0)
        rows = self.session.query(ReclamoGarantia).order_by(ReclamoGarantia.fecha_ingreso.desc()).limit(500).all()
        for rcl in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(str(rcl.id)))
            self.tbl.setItem(r, 1, QTableWidgetItem(str(rcl.garantia_id)))
            self.tbl.setItem(r, 2, QTableWidgetItem(rcl.fecha_ingreso.strftime("%d/%m/%Y %H:%M")))
            self.tbl.setItem(r, 3, QTableWidgetItem(rcl.estado or ""))
            self.tbl.setItem(r, 4, QTableWidgetItem(rcl.observaciones or ""))


# --------------------------
# Tab principal
# --------------------------
class GarantiasTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(GarantiasVigentesTab(), "Vigentes")
        self.tabs.addTab(ReclamosGarantiaTab(), "Reclamos")
        layout.addWidget(self.tabs)
