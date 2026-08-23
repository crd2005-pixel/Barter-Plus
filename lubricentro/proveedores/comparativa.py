# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from sqlalchemy import select
from .bootstrap import bootstrap

# Acceso a DB principal para % proveedor guardados por import_listas
from db import SessionLocal as AppSession, ConfigParam

_ns = bootstrap()
Proveedor = _ns["Proveedor"]
ListaPrecioProveedor = _ns["ListaPrecioProveedor"]
ItemListaProveedor = _ns["ItemListaProveedor"]
SessionLocal = _ns["SessionLocal"]

# ---- helpers de configuración ----
def _cfg_get(key: str, default: str = "0"):
    try:
        with AppSession() as s:
            row = s.query(ConfigParam).filter(ConfigParam.clave == key).first()
            return row.valor if row and row.valor not in ("", None) else default
    except Exception:
        return default

def _prov_pct(prov_id: int):
    try:
        d = float(_cfg_get(f"costos:{prov_id}:desc", "0"))
    except Exception:
        d = 0.0
    try:
        v = float(_cfg_get(f"costos:{prov_id}:iva", "21"))
    except Exception:
        v = 21.0
    return d, v


class ComparativaTab(QWidget):
    """
    Compara dos listas de precios por NETO proveedor:
    neto = lista * (1 - desc/100) * (1 + iva/100).
    """
    def __init__(self, on_send_to_productos=None, parent=None):
        super().__init__(parent)
        self._on_send_to_productos = on_send_to_productos
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        lay = QVBoxLayout(self)

        hdr = QHBoxLayout()
        self.cbo_lista1 = QComboBox(self)
        self.cbo_lista2 = QComboBox(self)
        self.btn_compare = QPushButton("Comparar listas")
        self.btn_send = QPushButton("Enviar a productos")
        hdr.addWidget(QLabel("Lista 1:"))
        hdr.addWidget(self.cbo_lista1, 1)
        hdr.addWidget(QLabel("Lista 2:"))
        hdr.addWidget(self.cbo_lista2, 1)
        hdr.addWidget(self.btn_compare)
        hdr.addWidget(self.btn_send)
        lay.addLayout(hdr)

        self.tbl = QTableWidget(self)
        self.tbl.setColumnCount(7)
        self.tbl.setHorizontalHeaderLabels(
            ["Código", "Descripción", "Precio 1", "Precio 2", "↓ Más bajo", "Proveedor 1 / 2", "Origen"]
        )
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setSelectionMode(QTableWidget.SingleSelection)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.tbl)

        self.btn_compare.clicked.connect(self._compare)
        self.btn_send.clicked.connect(self._send_selected)

    def _load_data(self):
        self.cbo_lista1.clear()
        self.cbo_lista2.clear()
        with SessionLocal() as s:
            rows = s.execute(
                select(ListaPrecioProveedor.id, ListaPrecioProveedor.nombre, ListaPrecioProveedor.proveedor_id)
                .order_by(ListaPrecioProveedor.id.desc())
            ).all()
            prov_cache = {}

            def _prov_name(pid):
                if pid in prov_cache:
                    return prov_cache[pid]
                p = s.get(Proveedor, pid)
                prov_cache[pid] = p.nombre if p else ""
                return prov_cache[pid]

            for lid, nombre, pid in rows:
                prov_name = _prov_name(pid)
                label = f"[{prov_name}] {nombre}" if prov_name else nombre
                self.cbo_lista1.addItem(label, lid)
                self.cbo_lista2.addItem(label, lid)

    def _compare(self):
        id1 = self.cbo_lista1.currentData()
        id2 = self.cbo_lista2.currentData()
        if not id1 or not id2:
            QMessageBox.warning(self, "Comparar", "Seleccione ambas listas.")
            return
        if id1 == id2:
            QMessageBox.warning(self, "Comparar", "Seleccione dos listas distintas.")
            return

        with SessionLocal() as s:
            col_code = getattr(ItemListaProveedor, "producto_codigo", None) or getattr(ItemListaProveedor, "codigo")
            col_price = getattr(ItemListaProveedor, "precio", None) or getattr(ItemListaProveedor, "prec")
            col_desc = getattr(ItemListaProveedor, "descripcion", None)

            items1 = {
                r[0]: (r[1], r[2] if len(r) > 2 else "")
                for r in s.execute(select(col_code, col_price, col_desc).where(ItemListaProveedor.lista_id == id1)).all()
                if r[0]
            }
            items2 = {
                r[0]: (r[1], r[2] if len(r) > 2 else "")
                for r in s.execute(select(col_code, col_price, col_desc).where(ItemListaProveedor.lista_id == id2)).all()
                if r[0]
            }

            lst1 = s.get(ListaPrecioProveedor, id1)
            lst2 = s.get(ListaPrecioProveedor, id2)
            prov1 = s.get(Proveedor, lst1.proveedor_id) if lst1 and lst1.proveedor_id else None
            prov2 = s.get(Proveedor, lst2.proveedor_id) if lst2 and lst2.proveedor_id else None
            name1 = prov1.nombre if prov1 else "(sin proveedor)"
            name2 = prov2.nombre if prov2 else "(sin proveedor)"
            d1, v1 = _prov_pct(prov1.id) if prov1 else (0.0, 21.0)
            d2, v2 = _prov_pct(prov2.id) if prov2 else (0.0, 21.0)

        diffs = []
        for cod, (p1, dsc1) in items1.items():
            if cod in items2:
                p2, dsc2 = items2[cod]
                try:
                    net1 = (float(p1) * (1 - d1/100.0) * (1 + v1/100.0)) if p1 is not None else None
                    net2 = (float(p2) * (1 - d2/100.0) * (1 + v2/100.0)) if p2 is not None else None
                    if net1 is not None and net2 is not None:
                        best = 1 if net1 <= net2 else 2
                    elif net1 is not None:
                        best = 1
                    elif net2 is not None:
                        best = 2
                    else:
                        best = 0
                except Exception:
                    best = 0
                diffs.append((cod, dsc1 or dsc2 or "", net1, net2, best, f"{name1} / {name2}", id1 if best == 1 else id2))

        self.tbl.setRowCount(len(diffs))
        green = QColor(198, 239, 206)
        for r, (cod, desc, p1, p2, best, provs, best_list_id) in enumerate(diffs):
            self.tbl.setItem(r, 0, QTableWidgetItem(str(cod)))
            self.tbl.setItem(r, 1, QTableWidgetItem("" if desc is None else str(desc)))
            it1 = QTableWidgetItem("" if p1 is None else f"{float(p1):.2f}")
            it2 = QTableWidgetItem("" if p2 is None else f"{float(p2):.2f}")
            if best == 1:
                it1.setBackground(green)
            elif best == 2:
                it2.setBackground(green)
            self.tbl.setItem(r, 2, it1)
            self.tbl.setItem(r, 3, it2)
            self.tbl.setItem(r, 4, QTableWidgetItem("1" if best == 1 else ("2" if best == 2 else "")))
            self.tbl.setItem(r, 5, QTableWidgetItem(provs))
            origin = QTableWidgetItem(str(best_list_id))
            origin.setData(Qt.UserRole, int(best_list_id))
            self.tbl.setItem(r, 6, origin)

    def _send_selected(self):
        row = self.tbl.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Productos", "Seleccione una fila.")
            return
        codigo = self.tbl.item(row, 0).text() if self.tbl.item(row, 0) else ""
        desc = self.tbl.item(row, 1).text() if self.tbl.item(row, 1) else ""
        best = self.tbl.item(row, 4).text() if self.tbl.item(row, 4) else ""
        precio = None
        if best == "1":
            precio = self.tbl.item(row, 2).text()
        elif best == "2":
            precio = self.tbl.item(row, 3).text()
        origen_item = self.tbl.item(row, 6)
        lista_id = origen_item.data(Qt.UserRole) if origen_item else None

        payload = {
            "codigo": codigo,
            "descripcion": desc,
            "precio": float(precio) if precio not in (None, "",) else None,
            "lista_id": int(lista_id) if lista_id else None,
        }

        if callable(self._on_send_to_productos):
            try:
                self._on_send_to_productos(payload)
                QMessageBox.information(self, "Productos", "Enviado a productos.")
            except Exception as e:
                QMessageBox.critical(self, "Productos", f"No se pudo enviar a productos.\n{e}")
        else:
            QMessageBox.information(self, "Productos", f"Seleccionado: {payload}")

# Alias esperado por main_tab.py
ComparativaListasTab = ComparativaTab
