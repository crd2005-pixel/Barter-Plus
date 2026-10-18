# service.py
# ===========================
# Módulo de Servicio Técnico
# ===========================

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QTextEdit,
    QTabWidget, QFormLayout
)
from PyQt5.QtCore import Qt
from db import SessionLocal, Service, Cliente, Producto


# --------------------------
# Ingreso de Servicios
# --------------------------
class IngresoTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.inp_cliente = QLineEdit()
        self.inp_producto = QLineEdit()
        self.inp_obs = QTextEdit()
        btn_add = QPushButton("Ingresar")
        btn_add.clicked.connect(self.add_service)

        form.addRow("Cliente:", self.inp_cliente)
        form.addRow("Producto:", self.inp_producto)
        form.addRow("Observaciones:", self.inp_obs)
        form.addRow(btn_add)

        layout.addLayout(form)

    def add_service(self):
        cliente = self.inp_cliente.text().strip()
        producto = self.inp_producto.text().strip()
        obs = self.inp_obs.toPlainText().strip()

        if not cliente:
            QMessageBox.warning(self, "Atención", "Debe ingresar un cliente")
            return

        with SessionLocal() as session:
            # Buscar o crear cliente
            cli = session.query(Cliente).filter(Cliente.nombre == cliente).first()
            if not cli:
                cli = Cliente(nombre=cliente)
                session.add(cli)
                session.commit()

            # Buscar producto (opcional)
            prod = None
            if producto:
                prod = session.query(Producto).filter(Producto.nombre == producto).first()

            # Crear registro de servicio
            s = Service(cliente=cli, producto=prod, observaciones=obs, estado="Ingresado")
            session.add(s)
            session.commit()

            QMessageBox.information(self, "OK", "Servicio ingresado correctamente")

        # Limpiar inputs
        self.inp_cliente.clear()
        self.inp_producto.clear()
        self.inp_obs.clear()


# --------------------------
# Seguimiento de Servicios
# --------------------------
class SeguimientoTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["ID", "Cliente", "Estado", "Observaciones"])
        layout.addWidget(self.tbl)

        btn = QPushButton("Actualizar")
        btn.clicked.connect(self.reload)
        layout.addWidget(btn)

        self.reload()

    def reload(self):
        self.tbl.setRowCount(0)
        with SessionLocal() as session:
            rows = session.query(Service).filter(Service.estado != "Entregado al cliente").all()
            for r in rows:
                row = self.tbl.rowCount()
                self.tbl.insertRow(row)
                self.tbl.setItem(row, 0, QTableWidgetItem(str(r.id)))
                self.tbl.setItem(row, 1, QTableWidgetItem(r.cliente.nombre if r.cliente else ""))
                self.tbl.setItem(row, 2, QTableWidgetItem(r.estado))
                self.tbl.setItem(row, 3, QTableWidgetItem(r.observaciones or ""))


# --------------------------
# Historial de Servicios
# --------------------------
class HistorialTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["ID", "Cliente", "Estado", "Observaciones"])
        layout.addWidget(self.tbl)

        btn = QPushButton("Actualizar")
        btn.clicked.connect(self.reload)
        layout.addWidget(btn)

        self.reload()

    def reload(self):
        self.tbl.setRowCount(0)
        with SessionLocal() as session:
            rows = session.query(Service).filter(Service.estado == "Entregado al cliente").all()
            for r in rows:
                row = self.tbl.rowCount()
                self.tbl.insertRow(row)
                self.tbl.setItem(row, 0, QTableWidgetItem(str(r.id)))
                self.tbl.setItem(row, 1, QTableWidgetItem(r.cliente.nombre if r.cliente else ""))
                self.tbl.setItem(row, 2, QTableWidgetItem(r.estado))
                self.tbl.setItem(row, 3, QTableWidgetItem(r.observaciones or ""))


# --------------------------
# Pestaña Principal
# --------------------------
class ServiceTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(IngresoTab(), "Ingreso")
        self.tabs.addTab(SeguimientoTab(), "Seguimiento")
        self.tabs.addTab(HistorialTab(), "Historial")

        layout.addWidget(self.tabs)
