# -*- coding: utf-8 -*-
"""
productos/promociones/base_promos.py

Vista unificada de promociones:
- ID = código de barras (mismo que Stock/Precios).
- “Código” = nombre del producto (visible/filtrable).
- “Precio base” = Precio Final de la pestaña Precios (numérico en UserRole, sin parsear texto).
- Tipo: Descuento $ (monto) o Descuento %.
- Al cambiar Tipo/Valor, se recalcula “Precio promo”. Si editás “Precio promo”, se recalcula el Valor.
- Guarda por (producto_id, fecha_inicio, fecha_fin) y recarga para verificar persistencia.
- Expira promos vencidas dejando valor=0 (y activo=False si existe ese campo).
"""

from datetime import date
from typing import Optional, Dict

from PyQt5.QtCore import Qt, QDate, QSettings
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QDoubleSpinBox, QDateEdit,
    QMessageBox, QLineEdit
)
from sqlalchemy import or_

from db import SessionLocal, Producto

# Modelo (ajustar import si tu ruta difiere)
try:
    from db.models.productos import PromocionProducto
except Exception:
    PromocionProducto = None

# Utilidades de Precios
try:
    from ..listas_bridge import find_price_plus_iva_for_product, get_stock_qty_for_product
except Exception:
    from productos.listas_bridge import find_price_plus_iva_for_product, get_stock_qty_for_product


# ---------------------- helpers: Producto / barcode ----------------------

def _get_barcode(p: Producto) -> str:
    return (
        getattr(p, "codigo_barras", None)
        or getattr(p, "barcode", None)
        or getattr(p, "cb", None)
        or getattr(p, "ean", None)
        or getattr(p, "codigo_barra", None)
        or getattr(p, "cod_barra", None)
        or ""
    )

def _get_producto_by_barcode(s, id_bar: str) -> Optional[Producto]:
    if not id_bar:
        return None
    conds = []
    for cname in ("codigo_barras", "barcode", "cb", "ean", "codigo_barra", "cod_barra"):
        col = getattr(Producto, cname, None)
        if col is not None:
            conds.append(col == id_bar)
    if not conds:
        return None
    return s.query(Producto).filter(or_(*conds)).first()


# ---------------------- cálculo “Precio Final” (Precios) -------------------

def _leer_ganancia_pct() -> float:
    try:
        st = QSettings("BarterPlus", "BarterPlus")
        val = st.value("productos/precios/ganancia_pct", None)
        return float(val) if val is not None else 0.0
    except Exception:
        return 0.0

def _total_prorrateable_mes() -> float:
    try:
        from productos.utils import total_prorrateable_mes as _tpm
    except Exception:
        from ..utils import total_prorrateable_mes as _tpm
    return float(_tpm() or 0.0)

def _denominador_total(s) -> float:
    denom = 0.0
    for p in s.query(Producto).all():
        try:
            info = find_price_plus_iva_for_product(p) or {}
            mas_iva = float(info.get("mas_iva", 0.0)) if isinstance(info, dict) else float(info or 0.0)
        except Exception:
            mas_iva = 0.0
        try:
            stk = float(get_stock_qty_for_product(p) or 0.0)
        except Exception:
            stk = 0.0
        if mas_iva > 0 and stk > 0:
            denom += mas_iva * stk
    return denom

def _precio_final_base(p: Producto, total_fijos: float, denom_total: float, ganancia_pct: float) -> float:
    """
    Precio Final (el de Precios, sin promo):
      mas_iva + prorrateo -> precio_cp
      precio_final = precio_cp / (1 - ganancia)
    """
    try:
        info = find_price_plus_iva_for_product(p) or {}
        mas_iva = float(info.get("mas_iva", 0.0)) if isinstance(info, dict) else float(info or 0.0)
    except Exception:
        mas_iva = 0.0
    try:
        stk = float(get_stock_qty_for_product(p) or 0.0)
    except Exception:
        stk = 0.0

    # Prorrateo desactivado por solicitud
    prorr = 0.0
    # if denom_total > 0 and mas_iva > 0 and stk > 0:
    #     prorr = total_fijos * ((mas_iva * stk) / denom_total)

    precio_cp = mas_iva + prorr
    gan = max(0.0, min(500.0, float(ganancia_pct))) / 100.0
    return float(precio_cp / (1.0 - gan)) if (1.0 - gan) > 1e-9 else float(precio_cp)


# -------------------------- lógica de promoción ---------------------------

def _calc_promo_from_valor(base: float, tipo_db: str, valor: float) -> float:
    """De Valor → Precio promo."""
    base = float(base or 0.0)
    valor = float(valor or 0.0)
    if tipo_db == "porcentaje":
        pct = max(0.0, min(valor, 100.0)) / 100.0
        return max(0.0, base * (1.0 - pct))
    # fijo ($): descuento directo
    return max(0.0, base - valor)

def _calc_valor_from_promo(base: float, tipo_db: str, precio_promo: float) -> float:
    """De Precio promo → Valor (monto o %)."""
    base = float(base or 0.0)
    precio_promo = float(precio_promo or 0.0)
    if base <= 0:
        return 0.0
    if tipo_db == "porcentaje":
        desc_pct = (1.0 - (precio_promo / base)) * 100.0
        return max(0.0, min(100.0, desc_pct))
    # fijo ($)
    desc_monto = base - precio_promo
    return max(0.0, desc_monto)


# ----------------------------- columnas UI --------------------------------

COL_ID       = 0  # barcode (no editable)
COL_CODIGO   = 1  # nombre (visible como “código”)
COL_NOMBRE   = 2  # nombre (duplicado)
COL_BASE     = 3  # Precio base (Precio Final) - QTableWidgetItem con UserRole=float
COL_TIPO     = 4  # QComboBox: "Descuento $" / "Descuento %"
COL_VALOR    = 5  # QDoubleSpinBox: monto o %
COL_PROMO    = 6  # QDoubleSpinBox: precio promo (resultado)
COL_INI      = 7  # QDateEdit
COL_FIN      = 8  # QDateEdit


# ----------------------- expiración de promos vencidas ---------------------

def _expire_outdated_promos(s):
    """Si fecha_fin < hoy y valor != 0 → valor=0 (y activo=False si existe)."""
    if not PromocionProducto:
        return
    hoy = date.today()
    changed = 0
    for pr in s.query(PromocionProducto).all():
        try:
            if pr.fecha_fin and pr.fecha_fin < hoy and float(pr.valor or 0.0) != 0.0:
                pr.valor = 0.0
                if hasattr(pr, "activo"):
                    pr.activo = False
                changed += 1
        except Exception:
            pass
    if changed:
        s.commit()


# --------------------------------- Widget ----------------------------------

class _PromosRubroTab(QWidget):
    """
    Una sola vista de promociones (sin rubros).
    Evita errores de coma/punto usando datos numéricos (UserRole y QDoubleSpinBox).
    """
    def __init__(self):
        super().__init__()
        self._rowcache: Dict[int, Dict] = {}  # por fila: {'pid': int, 'base': float}

        lay = QVBoxLayout(self)

        # Barra superior
        top = QHBoxLayout()
        top.addWidget(QLabel("Buscar productos:"))
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Código/Nombre/Marca...")
        btn_buscar = QPushButton("Buscar")
        btn_buscar.clicked.connect(self.cargar)
        self.btn_guardar = QPushButton("Guardar")
        self.btn_guardar.clicked.connect(self._guardar_todo)

        top.addWidget(self.txt_buscar, 1)
        top.addWidget(btn_buscar)
        top.addStretch(1)
        top.addWidget(self.btn_guardar)
        lay.addLayout(top)

        # Tabla
        self.tbl = QTableWidget(0, 9)
        self.tbl.setHorizontalHeaderLabels([
            "ID",            # barcode
            "Código",        # nombre (a pedido)
            "Nombre",        # idem
            "Precio base",   # Precio Final (numérico en UserRole)
            "Tipo",          # Descuento $ / %
            "Valor",         # monto o %
            "Precio promo",  # resultado editable
            "Inicio",
            "Fin"
        ])
        hdr = self.tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.verticalHeader().setVisible(False)

        lay.addWidget(self.tbl)
        self.setLayout(lay)

        self.cargar()

    # ----------------------------- carga -----------------------------------

    def _configure_valor_spin(self, sp: QDoubleSpinBox, is_pct: bool):
        sp.blockSignals(True)
        sp.setDecimals(2)
        if is_pct:
            sp.setRange(0.0, 100.0)
            sp.setSingleStep(0.5)
            sp.setSuffix(" %")
        else:
            sp.setRange(0.0, 1_000_000.0)
            sp.setSingleStep(10.0)
            sp.setSuffix("")
        sp.blockSignals(False)

    def _setup_precio_spin(self) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setDecimals(2)
        sp.setRange(0.0, 1_000_000_000.0)
        sp.setSingleStep(10.0)
        sp.setSuffix("")
        return sp

    def _hook_row_signals(self, row: int):
        """
        Enlace bidireccional SIN reemplazar widgets:
        - Cambia Tipo/Valor → recalcula Precio promo.
        - Cambia Precio promo → recalcula Valor (monto o %).
        Usa base numérica guardada en UserRole; sin nonlocal.
        """
        cb_tipo: QComboBox = self.tbl.cellWidget(row, COL_TIPO)
        sp_val: QDoubleSpinBox = self.tbl.cellWidget(row, COL_VALOR)
        sp_pro: QDoubleSpinBox = self.tbl.cellWidget(row, COL_PROMO)

        base_item = self.tbl.item(row, COL_BASE)
        base_num = float(base_item.data(Qt.UserRole) or 0.0)

        def to_db_tipo() -> str:
            return "fijo" if cb_tipo.currentIndex() == 0 else "porcentaje"

        def on_tipo_changed():
            is_pct = (cb_tipo.currentIndex() == 1)
            self._configure_valor_spin(sp_val, is_pct)
            # al cambiar tipo, recalcular desde el valor vigente
            on_valor_changed()

        def on_valor_changed():
            tipo_db = to_db_tipo()
            valor = float(sp_val.value() or 0.0)
            sp_pro.blockSignals(True)
            sp_pro.setValue(_calc_promo_from_valor(base_num, tipo_db, valor))
            sp_pro.blockSignals(False)

        def on_promo_changed():
            tipo_db = to_db_tipo()
            promo = float(sp_pro.value() or 0.0)
            sp_val.blockSignals(True)
            sp_val.setValue(_calc_valor_from_promo(base_num, tipo_db, promo))
            sp_val.blockSignals(False)

        cb_tipo.currentIndexChanged.connect(on_tipo_changed)
        sp_val.valueChanged.connect(on_valor_changed)
        sp_pro.valueChanged.connect(on_promo_changed)

        # configuración inicial y primer cálculo
        on_tipo_changed()

    def cargar(self):
        """Carga productos y prellena desde la última promo por producto (si existe)."""
        if not PromocionProducto:
            QMessageBox.warning(self, "Modelo faltante",
                                "No se encontró db.models.productos.PromocionProducto.")
            return

        ganancia_pct = _leer_ganancia_pct()
        with SessionLocal() as s:
            denom_total = _denominador_total(s)
            total_fijos = _total_prorrateable_mes()

            filtro = (self.txt_buscar.text() or "").strip().lower()
            self.tbl.setRowCount(0)
            self._rowcache.clear()

            prods = s.query(Producto).order_by(Producto.nombre.asc()).all()
            if filtro:
                tmp = []
                for p in prods:
                    campos = [
                        _get_barcode(p),
                        getattr(p, "codigo", None) or getattr(p, "sku", None) or getattr(p, "cod", None) or "",
                        getattr(p, "nombre", "") or "",
                        getattr(p, "marca", "") or "",
                    ]
                    if any(filtro in str(x).lower() for x in campos):
                        tmp.append(p)
                prods = tmp

            for p in prods:
                r = self.tbl.rowCount()
                self.tbl.insertRow(r)

                # ID (barcode)
                bid = _get_barcode(p)
                it_id = QTableWidgetItem(bid)
                it_id.setFlags(it_id.flags() ^ Qt.ItemIsEditable)
                self.tbl.setItem(r, COL_ID, it_id)

                # Código/Nombre
                nombre = getattr(p, "nombre", "") or ""
                self.tbl.setItem(r, COL_CODIGO, QTableWidgetItem(nombre))
                self.tbl.setItem(r, COL_NOMBRE, QTableWidgetItem(nombre))

                # Precio base (UserRole numérico, texto solo visual)
                base = _precio_final_base(p, total_fijos, denom_total, ganancia_pct)
                it_base = QTableWidgetItem(f"{base:.2f}")
                it_base.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                it_base.setFlags(it_base.flags() ^ Qt.ItemIsEditable)
                it_base.setData(Qt.UserRole, float(base))  # clave
                self.tbl.setItem(r, COL_BASE, it_base)

                # Tipo
                cb_tipo = QComboBox()
                cb_tipo.addItems(["Descuento $", "Descuento %"])
                self.tbl.setCellWidget(r, COL_TIPO, cb_tipo)

                # Valor (inicial en $)
                sp_val = QDoubleSpinBox()
                self.tbl.setCellWidget(r, COL_VALOR, sp_val)

                # Precio promo (editable)
                sp_pro = self._setup_precio_spin()
                self.tbl.setCellWidget(r, COL_PROMO, sp_pro)

                # Fechas
                de_ini = QDateEdit(); de_ini.setCalendarPopup(True); de_ini.setDisplayFormat("dd/MM/yyyy")
                de_fin = QDateEdit(); de_fin.setCalendarPopup(True); de_fin.setDisplayFormat("dd/MM/yyyy")
                self.tbl.setCellWidget(r, COL_INI, de_ini)
                self.tbl.setCellWidget(r, COL_FIN, de_fin)

                # Prellenado con última promo (si existe)
                pr = (s.query(PromocionProducto)
                        .filter(PromocionProducto.producto_id == p.id)
                        .order_by(PromocionProducto.fecha_inicio.desc())
                        .first())
                if pr:
                    cb_tipo.setCurrentIndex(0 if pr.tipo == "fijo" else 1)
                    # configurar spin según tipo y luego setear valor
                    self._configure_valor_spin(sp_val, pr.tipo == "porcentaje")
                    sp_val.setValue(float(pr.valor or 0.0))
                    if pr.fecha_inicio:
                        de_ini.setDate(QDate(pr.fecha_inicio.year, pr.fecha_inicio.month, pr.fecha_inicio.day))
                    else:
                        de_ini.setDate(QDate.currentDate())
                    if pr.fecha_fin:
                        de_fin.setDate(QDate(pr.fecha_fin.year, pr.fecha_fin.month, pr.fecha_fin.day))
                    else:
                        de_fin.setDate(QDate.currentDate())
                else:
                    # default: descuento $ = 0
                    self._configure_valor_spin(sp_val, False)
                    sp_val.setValue(0.0)
                    de_ini.setDate(QDate.currentDate())
                    de_fin.setDate(QDate.currentDate())

                # cache de fila
                self._rowcache[r] = {"pid": p.id, "base": float(base)}

                # señales (bidireccional y sin nonlocal)
                self._hook_row_signals(r)

    # ------------------------------ guardado --------------------------------

    def _guardar_todo(self):
        """Guarda por (producto_id, fecha_inicio, fecha_fin) y recarga para ver lo persistido."""
        if not PromocionProducto:
            QMessageBox.warning(self, "Modelo faltante",
                                "No se encontró db.models.productos.PromocionProducto.")
            return

        filas = self.tbl.rowCount()
        hoy = date.today()
        guardadas, errores = 0, []

        with SessionLocal() as s:
            for r in range(filas):
                try:
                    rowinfo = self._rowcache.get(r) or {}
                    pid = rowinfo.get("pid", None)
                    if pid is None:
                        # fallback por barcode
                        bid = (self.tbl.item(r, COL_ID).text() if self.tbl.item(r, COL_ID) else "").strip()
                        p = _get_producto_by_barcode(s, bid)
                        pid = p.id if p else None
                    if pid is None:
                        continue

                    cb_tipo: QComboBox = self.tbl.cellWidget(r, COL_TIPO)
                    sp_val: QDoubleSpinBox = self.tbl.cellWidget(r, COL_VALOR)
                    de_ini: QDateEdit = self.tbl.cellWidget(r, COL_INI)
                    de_fin: QDateEdit = self.tbl.cellWidget(r, COL_FIN)

                    f_ini = de_ini.date().toPyDate()
                    f_fin = de_fin.date().toPyDate()

                    # Busca por clave (producto_id, fechas); crea si no existe
                    pr = (s.query(PromocionProducto)
                            .filter(PromocionProducto.producto_id == pid)
                            .filter(PromocionProducto.fecha_inicio == f_ini)
                            .filter(PromocionProducto.fecha_fin == f_fin)
                            .first())
                    if not pr:
                        pr = PromocionProducto(
                            producto_id=pid,
                            tipo="fijo",
                            valor=0.0,
                            fecha_inicio=f_ini,
                            fecha_fin=f_fin
                        )
                        s.add(pr)
                        s.flush()

                    # mapear UI → DB
                    tipo_db = "fijo" if cb_tipo.currentIndex() == 0 else "porcentaje"
                    pr.tipo = tipo_db
                    pr.valor = float(sp_val.value() or 0.0)  # guarda el valor (monto o %)

                    # si el modelo tiene 'activo', setear por fechas + valor>0
                    if hasattr(pr, "activo"):
                        pr.activo = bool(
                            (pr.fecha_inicio is not None and pr.fecha_fin is not None)
                            and (pr.fecha_inicio <= hoy <= pr.fecha_fin)
                            and (float(pr.valor or 0.0) > 0.0)
                        )

                    guardadas += 1
                except Exception as e:
                    errores.append(f"Fila {r+1}: {e}")

            # commit
            try:
                s.commit()
            except Exception as e:
                errores.append(f"Commit: {e}")

        if errores:
            QMessageBox.warning(self, "Atención", "Algunas filas no se guardaron:\n- " + "\n- ".join(errores))
        else:
            # Recarga desde DB para ver exactamente lo persistido (incluye fechas)
            self.cargar()
            QMessageBox.information(self, "OK", f"Promociones guardadas ({guardadas} filas).")


class PromocionesRubroGroup(QWidget):
    """Contenedor unificado (una sola vista)."""
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(_PromosRubroTab())
        self.setLayout(lay)
