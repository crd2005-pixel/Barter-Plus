# filtros.py
# ===========================
# Módulo de Filtros para autos
# ===========================

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QComboBox, QGroupBox, QFormLayout,
    QMessageBox, QFileDialog, QTextEdit
)
from PyQt5.QtCore import Qt
from sqlalchemy import or_

from db import SessionLocal, Filtro, EquivalenciaFiltro


class FiltrosTab(QWidget):
    def __init__(self):
        super().__init__()
        self.session = SessionLocal()

        layout = QVBoxLayout(self)

        # --------------------------
        # Filtros de búsqueda
        # --------------------------
        fl = QGroupBox("Búsqueda avanzada")
        fl_lay = QFormLayout(fl)

        self.inp_codigo = QLineEdit(); self.inp_codigo.setPlaceholderText("Código exacto")
        self.inp_marca = QLineEdit(); self.inp_marca.setPlaceholderText("Marca (Prix, Tecneco, Wega, Wix, Fram...)")
        self.inp_vehiculo = QLineEdit(); self.inp_vehiculo.setPlaceholderText("Vehículo / Aplicación")
        self.inp_dim = QLineEdit(); self.inp_dim.setPlaceholderText("Dimensiones")

        btn_buscar = QPushButton("Buscar"); btn_buscar.clicked.connect(self.buscar)

        fl_lay.addRow("Código:", self.inp_codigo)
        fl_lay.addRow("Marca:", self.inp_marca)
        fl_lay.addRow("Vehículo:", self.inp_vehiculo)
        fl_lay.addRow("Dimensiones:", self.inp_dim)
        fl_lay.addRow(btn_buscar)

        layout.addWidget(fl)

        # --------------------------
        # Tabla principal
        # --------------------------
        self.tbl = QTableWidget(0, 7)
        self.tbl.setHorizontalHeaderLabels([
            "ID", "Código", "Marca", "Tipo", "Vehículo",
            "Dimensiones", "Precio"
        ])
        self.tbl.cellDoubleClicked.connect(self.ver_equivalencias)
        layout.addWidget(self.tbl)

        # --------------------------
        # Acciones
        # --------------------------
        hb = QHBoxLayout()
        btn_add = QPushButton("Nuevo filtro"); btn_add.clicked.connect(self.nuevo_filtro)
        btn_edit = QPushButton("Editar seleccionado"); btn_edit.clicked.connect(self.editar_filtro)
        btn_del = QPushButton("Eliminar"); btn_del.clicked.connect(self.eliminar_filtro)
        btn_reload = QPushButton("Recargar"); btn_reload.clicked.connect(self.reload)
        hb.addWidget(btn_add); hb.addWidget(btn_edit); hb.addWidget(btn_del); hb.addStretch(); hb.addWidget(btn_reload)
        layout.addLayout(hb)

        self.reload()

    # --------------------------
    # Funciones
    # --------------------------
    def reload(self):
        self.tbl.setRowCount(0)
        rows = self.session.query(Filtro).order_by(Filtro.marca.asc(), Filtro.codigo.asc()).limit(500).all()
        for f in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(str(f.id)))
            self.tbl.setItem(r, 1, QTableWidgetItem(f.codigo or ""))
            self.tbl.setItem(r, 2, QTableWidgetItem(f.marca or ""))
            self.tbl.setItem(r, 3, QTableWidgetItem(f.tipo or ""))
            self.tbl.setItem(r, 4, QTableWidgetItem(f.vehiculo or ""))
            self.tbl.setItem(r, 5, QTableWidgetItem(f.dimensiones or ""))
            self.tbl.setItem(r, 6, QTableWidgetItem(f"{f.precio:.2f}"))

    def buscar(self):
        codigo = self.inp_codigo.text().strip()
        marca = self.inp_marca.text().strip()
        veh = self.inp_vehiculo.text().strip()
        dim = self.inp_dim.text().strip()

        q = self.session.query(Filtro)
        if codigo:
            q = q.filter(Filtro.codigo.ilike(f"%{codigo}%"))
        if marca:
            q = q.filter(Filtro.marca.ilike(f"%{marca}%"))
        if veh:
            q = q.filter(Filtro.vehiculo.ilike(f"%{veh}%"))
        if dim:
            q = q.filter(Filtro.dimensiones.ilike(f"%{dim}%"))

        rows = q.limit(500).all()
        self.tbl.setRowCount(0)
        for f in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(str(f.id)))
            self.tbl.setItem(r, 1, QTableWidgetItem(f.codigo or ""))
            self.tbl.setItem(r, 2, QTableWidgetItem(f.marca or ""))
            self.tbl.setItem(r, 3, QTableWidgetItem(f.tipo or ""))
            self.tbl.setItem(r, 4, QTableWidgetItem(f.vehiculo or ""))
            self.tbl.setItem(r, 5, QTableWidgetItem(f.dimensiones or ""))
            self.tbl.setItem(r, 6, QTableWidgetItem(f"{f.precio:.2f}"))

    def nuevo_filtro(self):
        f = Filtro(
            codigo="NUEVO",
            marca="",
            descripcion="",
            tipo="",
            dimensiones="",
            vehiculo="",
            precio=0.0
        )
        self.session.add(f); self.session.commit()
        QMessageBox.information(self, "OK", f"Filtro creado con ID {f.id}")
        self.reload()

    def editar_filtro(self):
        r = self.tbl.currentRow()
        if r < 0:
            QMessageBox.warning(self, "Editar", "Seleccione un filtro.")
            return
        fid = int(self.tbl.item(r, 0).text())
        f = self.session.query(Filtro).get(fid)
        if not f: return

        # Tomar de la tabla los cambios
        f.codigo = self.tbl.item(r, 1).text()
        f.marca = self.tbl.item(r, 2).text()
        f.tipo = self.tbl.item(r, 3).text()
        f.vehiculo = self.tbl.item(r, 4).text()
        f.dimensiones = self.tbl.item(r, 5).text()
        try:
            f.precio = float(self.tbl.item(r, 6).text())
        except:
            f.precio = 0.0
        self.session.commit()
        QMessageBox.information(self, "OK", "Filtro actualizado.")

    def eliminar_filtro(self):
        r = self.tbl.currentRow()
        if r < 0:
            QMessageBox.warning(self, "Eliminar", "Seleccione un filtro.")
            return
        fid = int(self.tbl.item(r, 0).text())
        f = self.session.query(Filtro).get(fid)
        if f:
            self.session.delete(f); self.session.commit()
            QMessageBox.information(self, "OK", "Filtro eliminado.")
            self.reload()

    def ver_equivalencias(self, row, col):
        fid = int(self.tbl.item(row, 0).text())
        f = self.session.query(Filtro).get(fid)
        if not f: return

        eqs = self.session.query(EquivalenciaFiltro).filter_by(filtro_id=fid).all()
        if not eqs:
            QMessageBox.information(self, "Equivalencias", "No hay equivalencias cargadas.")
            return

        txt = f"Equivalencias de {f.codigo} ({f.marca}):\n"
        for e in eqs:
            txt += f"- {e.marca_equivalente} {e.codigo_equivalente}: {e.descripcion or ''}\n"
        QMessageBox.information(self, "Equivalencias", txt)
