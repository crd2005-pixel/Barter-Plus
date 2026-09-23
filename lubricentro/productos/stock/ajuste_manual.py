# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox, QLabel, QMessageBox, QFileDialog, QComboBox
)
from sqlalchemy import func
import pandas as pd

from db import SessionLocal, Producto, Stock, Deposito
from ..utils import ajustar_stock, precio_final_sugerido

# Disparo de autopedido (si está disponible)
try:
    from proveedores.pedidos import auto_pedido_por_bajo_stock
except Exception:
    auto_pedido_por_bajo_stock = None


# ----------------- helpers -----------------
def _as_float(x, d=0.0):
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return d

def _get(obj, *names, default=None):
    for n in names:
        if hasattr(obj, n):
            v = getattr(obj, n)
            try:
                return v() if callable(v) else v
            except Exception:
                pass
    return default

def _set_first(obj, pairs):
    for k, v in pairs:
        if hasattr(obj, k):
            try:
                setattr(obj, k, v)
                return True
            except Exception:
                pass
    return False


# --------------- UI principal ---------------
class AjusteManualTab(QWidget):
    """
    - Lista productos con stock.
    - Permite ajustar stock (positivo entra, negativo sale).
    - Edita presentación (cantidad y unidad) y stock mínimo.
    - Conversión del delta por presentación (base/presentación).
    - Dispara autopedido si queda <= mínimo.
    """
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # ----- Barra superior -----
        h = QHBoxLayout()
        self.inp_buscar = QLineEdit()
        self.inp_buscar.setPlaceholderText("Buscar producto…")
        self.cb_deposito = QComboBox()
        self._cargar_depositos()

        self.ed_delta = QLineEdit("-1")
        self.ed_delta.setToolTip("Cantidad a ajustar. Negativo = salida.")

        # NUEVO: modo de delta
        self.cb_modo_delta = QComboBox()
        self.cb_modo_delta.addItems(["base", "presentación"])  # base=litro/unidad; presentación=tacho/caja

        self.ed_pres_cant = QLineEdit("1")
        self.ed_pres_unid = QLineEdit("unidad")
        self.ed_stock_min = QLineEdit("0")

        self.btn_aplicar = QPushButton("Aplicar ajuste")
        self.btn_aplicar.clicked.connect(self._aplicar)
        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.clicked.connect(self.cargar)
        self.btn_export = QPushButton("Exportar CSV")
        self.btn_export.clicked.connect(self._exportar_csv)
        self.btn_import = QPushButton("Importar CSV")
        self.btn_import.clicked.connect(self._importar_csv)

        h.addWidget(QLabel("Depósito:"));  h.addWidget(self.cb_deposito, 0)
        h.addWidget(self.inp_buscar, 1)
        h.addWidget(QLabel("Δ:"));         h.addWidget(self.ed_delta, 0)
        h.addWidget(QLabel("en:"));        h.addWidget(self.cb_modo_delta, 0)  # NUEVO
        h.addWidget(QLabel("Pres.:"));     h.addWidget(self.ed_pres_cant, 0)
        h.addWidget(QLabel("Unidad:"));    h.addWidget(self.ed_pres_unid, 0)
        h.addWidget(QLabel("Mínimo:"));    h.addWidget(self.ed_stock_min, 0)
        h.addWidget(self.btn_aplicar, 0)
        h.addWidget(self.btn_refresh, 0)
        h.addWidget(self.btn_export, 0)
        h.addWidget(self.btn_import, 0)
        layout.addLayout(h)

        # ----- Tabla -----
        self.tbl = QTableWidget(0, 9)
        self.tbl.setHorizontalHeaderLabels([
            "ID", "Producto", "Depósito", "Stock", "Mínimo",
            "Pres.cant", "Unidad", "Costo", "Precio sug."
        ])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self.tbl)

        # eventos
        self.inp_buscar.textChanged.connect(self.cargar)
        self.cb_deposito.currentIndexChanged.connect(self.cargar)

        # cache de filas: pid -> row
        self._index = {}

        self.cargar()

    # ---------- data ----------
    def _cargar_depositos(self):
        self.cb_deposito.clear()
        self.cb_deposito.addItem("Todos", None)
        try:
            with SessionLocal() as s:
                for d in s.query(Deposito).order_by(Deposito.nombre.asc()).all():
                    self.cb_deposito.addItem(getattr(d, "nombre", f"Dep {getattr(d,'id','')}"), getattr(d, "id", None))
        except Exception:
            pass

    def _stock_query(self, s, prod_id=None, dep_id=None):
        q = s.query(
            Stock.producto_id,
            func.coalesce(func.sum(Stock.cantidad), 0.0).label("stk")
        )
        if prod_id is not None:
            q = q.filter(Stock.producto_id == prod_id)
        if dep_id:
            q = q.filter(Stock.deposito_id == dep_id)
        q = q.group_by(Stock.producto_id)
        return {pid: float(stk or 0.0) for pid, stk in q.all()}

    def cargar(self):
        buscar = (self.inp_buscar.text() or "").strip().lower()
        dep_id = self.cb_deposito.currentData()
        self.tbl.setRowCount(0)
        self._index.clear()

        with SessionLocal() as s:
            stocks = self._stock_query(s, dep_id=dep_id)
            prods = s.query(Producto).all()

            for p in prods:
                nombre = (getattr(p, "nombre", "") or "")
                if buscar and buscar not in nombre.lower():
                    continue

                pid = getattr(p, "id", None)
                stk = stocks.get(pid, 0.0)
                smin = _as_float(_get(p, "stock_minimo", "stock_min", "minimo", "stock_min_litros", default=0), 0)
                pcant = _as_float(_get(p, "presentacion_cant", "unidades_por_caja", "pack_cant",
                                       "litros_por_envase", "capacidad_litros", default=1), 1)
                punid = _get(p, "presentacion_unidad", "presentacion_tipo", "unidad", default="unidad")
                costo = _as_float(_get(p, "costo", "costo_unit", "ultimo_costo", default=0), 0)

                try:
                    psug = precio_final_sugerido(p)  # si tu función lo soporta
                except Exception:
                    psug = 0.0

                r = self.tbl.rowCount()
                self.tbl.insertRow(r)
                self.tbl.setItem(r, 0, QTableWidgetItem(str(pid or "")))
                self.tbl.setItem(r, 1, QTableWidgetItem(nombre))
                self.tbl.setItem(r, 2, QTableWidgetItem(self.cb_deposito.currentText() or "Todos"))
                self.tbl.setItem(r, 3, QTableWidgetItem(f"{stk:.2f}"))
                self.tbl.setItem(r, 4, QTableWidgetItem(f"{smin:.2f}"))
                self.tbl.setItem(r, 5, QTableWidgetItem(f"{pcant:.2f}"))
                self.tbl.setItem(r, 6, QTableWidgetItem(str(punid)))
                self.tbl.setItem(r, 7, QTableWidgetItem(f"{costo:.2f}"))
                self.tbl.setItem(r, 8, QTableWidgetItem(f"{_as_float(psug,0):.2f}"))

                self._index[pid] = r

    # ---------- selección ----------
    def _on_select(self):
        r = self._row_sel()
        if r is None:
            return
        try:
            self.ed_pres_cant.setText(self.tbl.item(r, 5).text())
            self.ed_pres_unid.setText(self.tbl.item(r, 6).text())
            self.ed_stock_min.setText(self.tbl.item(r, 4).text())
        except Exception:
            pass

    def _row_sel(self):
        rows = self.tbl.selectionModel().selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _pid_sel(self):
        r = self._row_sel()
        if r is None:
            return None
        try:
            return int(self.tbl.item(r, 0).text())
        except Exception:
            return None

    # ---------- acciones ----------
    def _aplicar(self):
        pid = self._pid_sel()
        if not pid:
            QMessageBox.information(self, "Ajuste", "Seleccioná un producto.")
            return

        delta_in = _as_float(self.ed_delta.text(), 0.0)
        if delta_in == 0.0:
            QMessageBox.information(self, "Ajuste", "Ingresá una cantidad distinta de cero.")
            return

        # guardar presentación y mínimo
        try:
            with SessionLocal() as s:
                p = s.query(Producto).get(pid)
                if not p:
                    QMessageBox.information(self, "Ajuste", "Producto inexistente.")
                    return
                pres_c = _as_float(self.ed_pres_cant.text(), 1.0)
                pres_u = (self.ed_pres_unid.text() or "unidad").strip()
                smin = _as_float(self.ed_stock_min.text(), 0.0)

                _set_first(p, [("presentacion_cant", pres_c)])
                _set_first(p, [("presentacion_unidad", pres_u),
                               ("presentacion_tipo", pres_u),
                               ("unidad", pres_u)])
                _set_first(p, [("stock_minimo", smin),
                               ("stock_min", smin),
                               ("minimo", smin),
                               ("stock_min_litros", smin)])
                s.commit()
        except Exception as e:
            QMessageBox.critical(self, "Ajuste", f"No se pudo guardar presentación/mínimo.\n{e}")
            return

        # conversión del delta si está en "presentación"
        delta = delta_in
        modo = (self.cb_modo_delta.currentText() or "base").lower()
        if modo == "presentación":
            try:
                pres_c = _as_float(self.ed_pres_cant.text(), 1.0)
                if pres_c <= 0:
                    pres_c = 1.0
                delta = delta_in * pres_c
            except Exception:
                delta = delta_in

        # aplicar ajuste
        try:
            ajustar_stock(pid, delta)
        except Exception as e:
            QMessageBox.critical(self, "Ajuste", f"No se pudo aplicar el ajuste de stock.\n{e}")
            return

        # autopedido
        try:
            if auto_pedido_por_bajo_stock is not None:
                auto_pedido_por_bajo_stock(pid)
        except Exception:
            pass

        self.cargar()
        QMessageBox.information(self, "Ajuste", "Ajuste aplicado.")

    # ---------- CSV ----------
    def _exportar_csv(self):
        try:
            path, _ = QFileDialog.getSaveFileName(self, "Exportar", "stock.csv", "CSV (*.csv)")
            if not path:
                return
            data = []
            for r in range(self.tbl.rowCount()):
                data.append({
                    "id": self.tbl.item(r, 0).text(),
                    "producto": self.tbl.item(r, 1).text(),
                    "deposito": self.tbl.item(r, 2).text(),
                    "stock": self.tbl.item(r, 3).text(),
                    "minimo": self.tbl.item(r, 4).text(),
                    "pres_cant": self.tbl.item(r, 5).text(),
                    "unidad": self.tbl.item(r, 6).text(),
                    "costo": self.tbl.item(r, 7).text(),
                    "precio_sug": self.tbl.item(r, 8).text(),
                })
            pd.DataFrame(data).to_csv(path, index=False, encoding="utf-8")
            QMessageBox.information(self, "Exportar", "CSV generado.")
        except Exception as e:
            QMessageBox.critical(self, "Exportar", f"No se pudo exportar.\n{e}")

    def _importar_csv(self):
        try:
            path, _ = QFileDialog.getOpenFileName(self, "Importar", "", "CSV (*.csv)")
            if not path:
                return
            df = pd.read_csv(path, dtype=str)
            with SessionLocal() as s:
                for _, row in df.iterrows():
                    try:
                        pid = int(row.get("id"))
                    except Exception:
                        continue
                    p = s.query(Producto).get(pid)
                    if not p:
                        continue
                    # mínimos y presentación desde CSV si vienen
                    smin = _as_float(row.get("minimo"), None)
                    if smin is not None:
                        _set_first(p, [("stock_minimo", smin),
                                       ("stock_min", smin),
                                       ("minimo", smin),
                                       ("stock_min_litros", smin)])
                    pc = _as_float(row.get("pres_cant"), None)
                    if pc is not None:
                        _set_first(p, [("presentacion_cant", pc)])
                    pu = (row.get("unidad") or "").strip()
                    if pu:
                        _set_first(p, [("presentacion_unidad", pu),
                                       ("presentacion_tipo", pu),
                                       ("unidad", pu)])
                s.commit()
            self.cargar()
            QMessageBox.information(self, "Importar", "CSV importado.")
        except Exception as e:
            QMessageBox.critical(self, "Importar", f"No se pudo importar.\n{e}")
