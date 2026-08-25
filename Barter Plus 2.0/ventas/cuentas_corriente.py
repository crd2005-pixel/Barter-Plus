# -*- coding: utf-8 -*-
# ventas/cuentas_corriente.py
# Cuentas Corrientes + CRUD de planes de tarjeta con filtros
# Incluye migración automática desde tablas legadas (tarjeta_plan/tarjeta_planes/tarjetas)
# para que aparezca lo ya cargado y se pueda modificar.

import datetime as dt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QGridLayout,
    QLineEdit, QSpinBox, QDoubleSpinBox, QMessageBox,
    QComboBox, QCheckBox
)
from PyQt5.QtCore import Qt
from sqlalchemy import func, text

# DB
from db import SessionLocal, Cliente, CuentaCorrienteCliente
# Import robusto del modelo de tarjetas
try:
    from db import TarjetaCoef  # expuesto en db/__init__.py
except Exception:
    try:
        from db.models.tarjetas import TarjetaCoef  # ruta directa del modelo
    except Exception:
        TarjetaCoef = None


# ----------------------- Diálogo de movimientos por cliente -----------------------
class MovimientosCCDialog(QDialog):
    def __init__(self, cliente_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Movimientos de cuenta corriente")
        self.resize(900, 520)
        self.cliente_id = cliente_id

        lay = QVBoxLayout(self)
        self.lbl_saldo = QLabel("Saldo: $0,00")
        self.lbl_saldo.setAlignment(Qt.AlignLeft)
        lay.addWidget(self.lbl_saldo)

        self.tbl = QTableWidget(0, 5, self)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Concepto", "Débito", "Crédito", "Saldo"])
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.tbl)

        self.reload()

    def _f(self, x):
        try:
            return f"{float(x):.2f}"
        except Exception:
            return "0.00"

    def reload(self):
        with SessionLocal() as s:
            movs = (
                s.query(CuentaCorrienteCliente)
                .filter(CuentaCorrienteCliente.cliente_id == self.cliente_id)
                .order_by(CuentaCorrienteCliente.fecha.asc(), CuentaCorrienteCliente.id.asc())
                .all()
            )

        saldo = 0.0
        self.tbl.setRowCount(0)
        for m in movs:
            monto = float(m.monto or 0.0)
            deb = monto if monto > 0 else 0.0
            hab = -monto if monto < 0 else 0.0
            saldo += monto
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            fecha = (m.fecha or dt.datetime.utcnow()).strftime("%d/%m/%Y %H:%M")
            self.tbl.setItem(r, 0, QTableWidgetItem(fecha))
            self.tbl.setItem(r, 1, QTableWidgetItem(m.concepto or ""))
            self.tbl.setItem(r, 2, QTableWidgetItem(self._f(deb)))
            self.tbl.setItem(r, 3, QTableWidgetItem(self._f(hab)))
            self.tbl.setItem(r, 4, QTableWidgetItem(self._f(saldo)))
            for c in range(5):
                it = self.tbl.item(r, c)
                it.setTextAlignment(Qt.AlignCenter if c != 1 else Qt.AlignLeft | Qt.AlignVCenter)

        self.lbl_saldo.setText(f"Saldo: ${saldo:.2f}")


# ----------------------- Utilidades de migración de tablas legadas -----------------------
def _list_tables(conn):
    rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    return {r[0] for r in rows}

def _table_columns(conn, table):
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    # devuelve dict nombre_col -> tipo
    return {r[1]: r[2] for r in rows}

def _first_present(candidates, available):
    for c in candidates:
        if c in available:
            return c
    return None

def _migrate_legacy_planes_if_needed():
    if TarjetaCoef is None:
        return

    with SessionLocal() as s:
        # Si ya hay planes, no migrar
        try:
            has_any = s.query(TarjetaCoef.id).limit(1).first() is not None
        except Exception:
            has_any = False
        if has_any:
            return

        engine = s.bind
        if engine is None:
            return

        try:
            with engine.connect() as conn:
                tables = _list_tables(conn)
                # Candidatos de tablas legadas
                legacy_candidates = [
                    "tarjeta_plan", "tarjeta_planes", "tarjetas_plan",
                    "tarjetas_planes", "tarjetas", "tarjeta"
                ]
                found = [t for t in legacy_candidates if t in tables]
                if not found:
                    return  # no hay legados

                inserted = 0
                for t in found:
                    cols = _table_columns(conn, t)
                    if not cols:
                        continue
                    # Posibles nombres de columnas
                    marca_col = _first_present(
                        ["marca", "tarjeta", "nombre", "brand"], cols
                    )
                    cuotas_col = _first_present(
                        ["cuotas", "cuota", "n_cuotas", "cant_cuotas"], cols
                    )
                    recargo_col = _first_present(
                        ["recargo_pct", "recargo", "porcentaje", "coef", "interes", "interes_pct"], cols
                    )
                    if not (marca_col and cuotas_col and recargo_col):
                        continue

                    try:
                        q = text(
                            f"SELECT {marca_col} as marca, {cuotas_col} as cuotas, {recargo_col} as recargo FROM {t}"
                        )
                        rows = conn.execute(q).fetchall()
                    except Exception:
                        continue

                    for r in rows:
                        try:
                            marca = (r[0] or "").strip()
                            cuotas = int(r[1] or 0)
                            recargo = float(r[2] or 0.0)
                        except Exception:
                            continue
                        if not marca or cuotas < 1:
                            continue
                        # Evitar duplicados: (marca, cuotas)
                        exist = (
                            s.query(TarjetaCoef)
                            .filter(TarjetaCoef.marca == marca, TarjetaCoef.cuotas == cuotas)
                            .first()
                        )
                        if exist:
                            # preferimos mantener el que viene si en la base nueva no había nada
                            exist.recargo_pct = recargo
                        else:
                            s.add(TarjetaCoef(marca=marca, cuotas=cuotas, recargo_pct=recargo))
                        inserted += 1
                if inserted:
                    s.commit()
        except Exception:
            # No interrumpir la UI si falla la migración
            pass


# ----------------------- Diálogo CRUD de planes de tarjeta con filtros -----------------------
class PlanesTarjetaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Planes de tarjeta (cuotas y %)")
        self.resize(760, 560)

        if TarjetaCoef is None:
            QMessageBox.critical(self, "Tarjetas", "No se encontró el modelo TarjetaCoef en la DB.")
            self.close()
            return

        # Migración automática (si TarjetaCoef está vacío intenta traer de tablas legadas)
        _migrate_legacy_planes_if_needed()

        root = QVBoxLayout(self)

        # ---------- Filtros ----------
        filtros = QHBoxLayout()
        filtros.addWidget(QLabel("Marca"))
        self.cb_marca = QComboBox()
        self.cb_marca.addItem("Todas")
        filtros.addWidget(self.cb_marca)

        filtros.addWidget(QLabel("Cuotas"))
        self.sp_cuotas = QSpinBox()
        self.sp_cuotas.setRange(1, 120)
        self.sp_cuotas.setValue(1)
        filtros.addWidget(self.sp_cuotas)

        self.chk_todas_cuotas = QCheckBox("Todas")
        self.chk_todas_cuotas.setChecked(True)
        filtros.addWidget(self.chk_todas_cuotas)

        self.btn_aplicar = QPushButton("Aplicar filtros")
        self.btn_limpiar = QPushButton("Limpiar")
        filtros.addStretch(1)
        filtros.addWidget(self.btn_aplicar)
        filtros.addWidget(self.btn_limpiar)
        root.addLayout(filtros)

        self.btn_aplicar.clicked.connect(self._apply_filters)
        self.btn_limpiar.clicked.connect(self._clear_filters)

        # ---------- Tabla ----------
        self.tbl = QTableWidget(0, 3, self)
        self.tbl.setHorizontalHeaderLabels(["Marca", "Cuotas", "Recargo %"])
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.cellClicked.connect(self._on_tbl_click)
        root.addWidget(self.tbl)

        # ---------- Formulario ----------
        form = QGridLayout()
        form.addWidget(QLabel("Marca"), 0, 0)
        self.in_marca = QLineEdit()
        form.addWidget(self.in_marca, 0, 1)

        form.addWidget(QLabel("Cuotas"), 1, 0)
        self.in_cuotas = QSpinBox()
        self.in_cuotas.setRange(1, 120)
        form.addWidget(self.in_cuotas, 1, 1)

        form.addWidget(QLabel("Recargo %"), 2, 0)
        self.in_recargo = QDoubleSpinBox()
        self.in_recargo.setRange(-1000.0, 1000.0)
        self.in_recargo.setDecimals(2)
        self.in_recargo.setSingleStep(0.25)
        form.addWidget(self.in_recargo, 2, 1)
        root.addLayout(form)

        # ---------- Botones CRUD ----------
        btns = QHBoxLayout()
        self.btn_nuevo = QPushButton("Nuevo")
        self.btn_guardar = QPushButton("Guardar / Actualizar")
        self.btn_eliminar = QPushButton("Eliminar")
        self.btn_cerrar = QPushButton("Cerrar")

        self.btn_nuevo.clicked.connect(self._nuevo)
        self.btn_guardar.clicked.connect(self._guardar)
        self.btn_eliminar.clicked.connect(self._eliminar)
        self.btn_cerrar.clicked.connect(self.accept)

        btns.addWidget(self.btn_nuevo)
        btns.addWidget(self.btn_guardar)
        btns.addWidget(self.btn_eliminar)
        btns.addStretch(1)
        btns.addWidget(self.btn_cerrar)
        root.addLayout(btns)

        # Estado
        self._selected_id = None

        # Inicialización
        self._load_distinct_marcas()
        self.reload()  # sin filtros

    # ===== helpers =====
    def _load_distinct_marcas(self):
        self.cb_marca.blockSignals(True)
        self.cb_marca.clear()
        self.cb_marca.addItem("Todas")
        with SessionLocal() as s:
            marcas = [m[0] for m in s.query(TarjetaCoef.marca).distinct().order_by(TarjetaCoef.marca.asc()).all()]
        for m in marcas:
            if m:
                self.cb_marca.addItem(m)
        self.cb_marca.blockSignals(False)

    def _current_filters(self):
        marca = None
        cuotas = None
        m_text = self.cb_marca.currentText().strip() if self.cb_marca.currentIndex() >= 0 else "Todas"
        if m_text and m_text != "Todas":
            marca = m_text
        if not self.chk_todas_cuotas.isChecked():
            cuotas = int(self.sp_cuotas.value())
        return {"marca": marca, "cuotas": cuotas}

    def _apply_filters(self):
        self.reload(self._current_filters())

    def _clear_filters(self):
        self.cb_marca.setCurrentIndex(0)
        self.chk_todas_cuotas.setChecked(True)
        self.sp_cuotas.setValue(1)
        self.reload()

    def _clear_form(self):
        self._selected_id = None
        self.in_marca.clear()
        self.in_cuotas.setValue(1)
        self.in_recargo.setValue(0.0)

    def _on_tbl_click(self, row, col):
        it_marca = self.tbl.item(row, 0)
        it_cuotas = self.tbl.item(row, 1)
        it_recargo = self.tbl.item(row, 2)
        if not it_marca:
            return
        self._selected_id = it_marca.data(Qt.UserRole)
        self.in_marca.setText(it_marca.text())
        try:
            self.in_cuotas.setValue(int(it_cuotas.text()))
        except Exception:
            self.in_cuotas.setValue(1)
        try:
            self.in_recargo.setValue(float(it_recargo.text().replace(",", ".")))
        except Exception:
            self.in_recargo.setValue(0.0)

    def _nuevo(self):
        self._clear_form()
        self.in_marca.setFocus()

    def _validar(self):
        marca = (self.in_marca.text() or "").strip()
        cuotas = int(self.in_cuotas.value())
        recargo = float(self.in_recargo.value())
        if not marca:
            QMessageBox.warning(self, "Validación", "Ingrese la marca.")
            return None
        if cuotas < 1:
            QMessageBox.warning(self, "Validación", "Las cuotas deben ser ≥ 1.")
            return None
        return marca, cuotas, recargo

    def _guardar(self):
        val = self._validar()
        if not val:
            return
        marca, cuotas, recargo = val
        keep_filters = self._current_filters()

        with SessionLocal() as s:
            if self._selected_id:
                obj = s.get(TarjetaCoef, self._selected_id)
                if not obj:
                    QMessageBox.warning(self, "Tarjetas", "No se encontró el registro seleccionado.")
                    return
                obj.marca = marca
                obj.cuotas = cuotas
                obj.recargo_pct = recargo
                s.commit()
            else:
                existente = (
                    s.query(TarjetaCoef)
                    .filter(TarjetaCoef.marca == marca, TarjetaCoef.cuotas == cuotas)
                    .first()
                )
                if existente:
                    existente.recargo_pct = recargo
                else:
                    s.add(TarjetaCoef(marca=marca, cuotas=cuotas, recargo_pct=recargo))
                s.commit()

        self._load_distinct_marcas()
        self.reload(keep_filters)
        self._clear_form()

    def _eliminar(self):
        if not self._selected_id:
            QMessageBox.information(self, "Tarjetas", "Seleccione un plan para eliminar.")
            return
        if QMessageBox.question(self, "Confirmar", "¿Eliminar el plan seleccionado?") != QMessageBox.Yes:
            return
        keep_filters = self._current_filters()
        with SessionLocal() as s:
            obj = s.get(TarjetaCoef, self._selected_id)
            if obj:
                s.delete(obj)
                s.commit()
        self._load_distinct_marcas()
        self.reload(keep_filters)
        self._clear_form()

    def reload(self, filtros: dict = None):
        self.tbl.setRowCount(0)
        with SessionLocal() as s:
            q = s.query(TarjetaCoef)
            if filtros:
                if filtros.get("marca"):
                    q = q.filter(TarjetaCoef.marca == filtros["marca"])
                if filtros.get("cuotas") is not None:
                    q = q.filter(TarjetaCoef.cuotas == int(filtros["cuotas"]))
            planes = q.order_by(TarjetaCoef.marca.asc(), TarjetaCoef.cuotas.asc()).all()

        for p in planes:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            it_marca = QTableWidgetItem(p.marca or "")
            it_marca.setData(Qt.UserRole, getattr(p, "id", None))
            it_cuotas = QTableWidgetItem(str(getattr(p, "cuotas", 0)))
            it_rec = QTableWidgetItem(f"{float(getattr(p, 'recargo_pct', 0.0)):.2f}")
            for c, it in enumerate((it_marca, it_cuotas, it_rec)):
                self.tbl.setItem(r, c, it)
                it.setTextAlignment(Qt.AlignCenter if c != 0 else Qt.AlignLeft | Qt.AlignVCenter)


# ----------------------- Pestaña de Cuentas Corrientes -----------------------
class CuentasCorrienteTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CuentasCorrienteTab")

        layout = QVBoxLayout(self)

        # Encabezado: total saldos + botones
        top = QHBoxLayout()
        self.lbl_total = QLabel("Total saldos: $0,00")
        self.lbl_total.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.btn_planes = QPushButton("Planes tarjetas")
        self.btn_planes.clicked.connect(self._open_planes)

        btn_reload = QPushButton("Actualizar")
        btn_reload.clicked.connect(self.reload)

        top.addWidget(self.lbl_total)
        top.addStretch(1)
        top.addWidget(self.btn_planes)
        top.addWidget(btn_reload)
        layout.addLayout(top)

        # Tabla de resumen de clientes con CC
        self.tbl = QTableWidget(0, 3, self)
        self.tbl.setHorizontalHeaderLabels(["Cliente", "CUIT/DNI", "Saldo"])
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.cellDoubleClicked.connect(self._open_dialog)
        layout.addWidget(self.tbl)

        self.reload()

    def _f(self, x):
        try:
            return f"{float(x):.2f}"
        except Exception:
            return "0.00"

    def _rows_resumen(self):
        with SessionLocal() as s:
            sums = (
                s.query(CuentaCorrienteCliente.cliente_id, func.sum(CuentaCorrienteCliente.monto))
                .group_by(CuentaCorrienteCliente.cliente_id)
                .all()
            )
            if not sums:
                return []
            saldos = {cid: float(total or 0.0) for cid, total in sums}
            cids = list(saldos.keys())
            if not cids:
                return []
            clientes = s.query(Cliente).filter(Cliente.id.in_(cids)).all()
            info = {c.id: c for c in clientes}

        rows = []
        for cid, saldo in saldos.items():
            c = info.get(cid)
            nombre = getattr(c, "nombre", "") if c else ""
            cuit = getattr(c, "cuit_dni", "") if c else ""
            rows.append((cid, nombre, cuit, saldo))
        rows.sort(key=lambda t: (t[1] or "").lower())
        return rows

    def reload(self):
        rows = self._rows_resumen()
        self.tbl.setRowCount(0)
        total = 0.0
        for cid, nombre, cuit, saldo in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            it0 = QTableWidgetItem(nombre or "")
            it1 = QTableWidgetItem(cuit or "")
            it2 = QTableWidgetItem(self._f(saldo))
            it0.setData(Qt.UserRole, cid)
            for it, idx in ((it0, 0), (it1, 1), (it2, 2)):
                self.tbl.setItem(r, idx, it)
                it.setTextAlignment(Qt.AlignCenter if idx != 0 else Qt.AlignLeft | Qt.AlignVCenter)
            total += saldo
        self.lbl_total.setText(f"Total saldos: ${total:.2f}")

    def _open_dialog(self, row, col):
        item = self.tbl.item(row, 0)
        if not item:
            return
        cliente_id = item.data(Qt.UserRole)
        if not cliente_id:
            return
        dlg = MovimientosCCDialog(cliente_id, self)
        dlg.exec_()
        self.reload()

    def _open_planes(self):
        if TarjetaCoef is None:
            QMessageBox.critical(self, "Tarjetas", "No se encontró el modelo TarjetaCoef en la DB.")
            return
        dlg = PlanesTarjetaDialog(self)
        dlg.exec_()
