# -*- coding: utf-8 -*-
"""
productos/precios_tab.py

Pestaña de precios:
- Lista productos de la DB principal.
- Toma +IVA desde listas de proveedores (proveedores/import_listas + proveedores/costos).
- Toma automáticamente el total de gastos fijos mensuales desde Costos → Gastos fijos
  (Impuestos + Gastos de negocio + Sueldos).
- Prorratea esos gastos fijos sobre el stock valorizado (+IVA) y aplica un % de ganancia global.

Fórmulas por producto i:
  base_i       = +IVA_i * stock_i
  denom        = Σ base_j   (sobre todos los productos con stock>0 y +IVA>0)
  prorr_i      = TotalGastosFijos * (base_i / denom)
  precio_cp_i  = +IVA_i + prorr_i
  precio_fin_i = precio_cp_i / (1 - Ganancia)

No pide “gastos variables” manuales. Los gastos variables son las listas mismas.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QDialogButtonBox, QMessageBox, QMenu, QInputDialog
)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtGui import QPagedPaintDevice, QFont

from PyQt5.QtWidgets import QApplication
from db import SessionLocal as AppSession, SessionLocal, Producto
from .listas_bridge import find_price_plus_iva_for_product, get_stock_qty_for_product, enable_cache
from .utils import total_prorrateable_mes  # (se usa en tu recálculo de tabla)

from productos.utils import (
    precio_final_sugerido,
    costo_proveedor_iva_descuento,
    total_prorrateable_mes as tpm_utils,
    mapa_stock_valor,
    prorrateo_cuota,
    margen_por_rubro,
    promocion_vigente,
)

def _fmt(x):
    try:
        return f"{float(x):.2f}"
    except Exception:
        return "0.00"


class PreciosTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._prods = []
        self._setup_ui()

        # ===== Persistencia de ganancia (tu lógica, intacta) =====
        self._settings = QSettings("BarterPlus", "BarterPlus")
        try:
            saved = self._settings.value("productos/precios/ganancia_pct", None, type=float)
        except TypeError:
            val = self._settings.value("productos/precios/ganancia_pct", None)
            saved = float(val) if val is not None else None
        if saved is not None:
            self.sp_gan.setValue(saved)
        self.sp_gan.valueChanged.connect(self._save_gain)
        # =========================================================

        self._load_products()

        # Cableo no intrusivo del botón "Consultar precio" sin depender del nombre exacto
        self._wire_consultar_precio()

    def showEvent(self, event):
        self._load_products()
        super().showEvent(event)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self):
        lay = QVBoxLayout(self)

        # Línea superior: gastos fijos (automático) + ganancia
        top = QHBoxLayout()
        self.lbl_fijos = QLabel("Gastos fijos mes: $0,00")
        top.addWidget(self.lbl_fijos)

        top.addSpacing(20)
        top.addWidget(QLabel("Ganancia (%):"))
        self.sp_gan = QDoubleSpinBox(self)
        self.sp_gan.setRange(0.0, 500.0)
        self.sp_gan.setDecimals(2)
        self.sp_gan.setSingleStep(0.5)
        self.sp_gan.setSuffix(" %")
        self.sp_gan.setValue(0.0)
        top.addWidget(self.sp_gan)

        top.addSpacing(20)
        self.btn_calc = QPushButton("Recalcular")
        top.addWidget(self.btn_calc)
        self.btn_pdf = QPushButton("Exportar PDF")
        top.addWidget(self.btn_pdf)
        top.addStretch(1)
        lay.addLayout(top)

        # Tabla de precios
        self.tbl = QTableWidget(self)
        self.tbl.setColumnCount(14)
        self.tbl.setHorizontalHeaderLabels([
            "ID", "Código", "Nombre", "Marca lista", "Lista ID",
            "Costo lista", "Desc.%", "IVA.%", "+IVA",
            "Stock", "Prorrateo", "Precio c/prorr.", "Calculado", "Precio final"
        ])
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setSelectionMode(QTableWidget.SingleSelection)
        self.tbl.setSortingEnabled(True)
        self.tbl.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._on_context_menu)
        self.tbl.verticalHeader().setVisible(False)
        header = self.tbl.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        lay.addWidget(self.tbl)

        self.btn_calc.clicked.connect(self._on_recalc_clicked)  # guarda y recalcula
        self.btn_pdf.clicked.connect(self._export_pdf)

        self.setLayout(lay)

    # ------------------------------------------------------------------
    # Persistencia de ganancia
    # ------------------------------------------------------------------
    def _save_gain(self):
        try:
            self._settings.setValue("productos/precios/ganancia_pct", float(self.sp_gan.value()))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def _load_products(self):
        # Lee productos desde la DB principal
        with AppSession() as s:
            self._prods = s.query(Producto).all()

        enable_cache()

        datos = []
        for i, p in enumerate(self._prods):
            if i % 100 == 0:
                QApplication.processEvents()

            info = find_price_plus_iva_for_product(p)  # cruza por proveedor_id+codigo, luego código, luego nombre
            stock = get_stock_qty_for_product(p)

            # ID = código de barras (misma clave que en Stock); si no hay, queda vacío (string)
            id_barcode = (
                getattr(p, "codigo_barras", None)
                or getattr(p, "barcode", None)
                or getattr(p, "cb", None)
                or getattr(p, "ean", None)
                or ""
            )

            # Código = el "código" de Stock (no el barcode)
            codigo_stock = (
                getattr(p, "codigo", None)
                or getattr(p, "sku", None)
                or getattr(p, "cod", None)
                or ""
            )

            datos.append({
                "pk": p.id,                               # ID real de DB (para updates)
                "id": id_barcode,                         # columna "ID" queda como barcode (string)
                "codigo": codigo_stock,                   # código de Stock (clave operativa)
                "nombre": getattr(p, "nombre", "") or "",
                "marca": info.get("marca", ""),
                "lista_id": info.get("lista_id", None),
                "base": float(info.get("base", 0.0)),        # costo lista
                "desc_pct": float(info.get("desc_pct", 0.0)),
                "iva_pct": float(info.get("iva_pct", 0.0)),
                "mas_iva": float(info.get("mas_iva", 0.0)),  # +IVA listo para prorratear
                "stock": float(stock or 0.0),
                "prorr": 0.0,
                "precio_cp": 0.0,
                "calculado": 0.0,
                "final": 0.0,
                "precio_manual": float(getattr(p, "precio_manual", 0.0) or 0.0),
                "venta_granel": bool(getattr(p, "venta_granel", 0) in (1, True, "1")),
                "presentacion_cantidad": float(getattr(p, "presentacion_cantidad", 1.0) or 1.0),
            })

        self._rows = datos
        self._render_table()
        self._recalc_all()  # primer cálculo automático

    def _render_table(self):
        # Desconectar señal para evitar bucles al repoblar
        try:
            self.tbl.itemChanged.disconnect(self._on_item_changed)
        except Exception:
            pass

        self.tbl.setRowCount(len(self._rows))

        for r, row in enumerate(self._rows):
            def setc(col, val, align_right=False, editable=False):
                text = "" if val is None else str(val)
                item = QTableWidgetItem(text)
                flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
                if editable:
                    flags |= Qt.ItemIsEditable
                item.setFlags(flags)

                if align_right:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif col in (0, 4, 9):
                    item.setTextAlignment(Qt.AlignCenter)

                # Guardar PK en la columna 13 (Precio Final) para identificar fila al editar
                if col == 13:
                    item.setData(Qt.UserRole, row["pk"])

                self.tbl.setItem(r, col, item)

            setc(0, row["id"])
            setc(1, row["codigo"])
            setc(2, row["nombre"])
            setc(3, row["marca"])
            setc(4, row["lista_id"])
            setc(5, _fmt(row["base"]), True)
            setc(6, _fmt(row["desc_pct"]), True)
            setc(7, _fmt(row["iva_pct"]), True)
            setc(8, _fmt(row["mas_iva"]), True)
            setc(9, _fmt(row["stock"]), True)
            setc(10, _fmt(row["prorr"]), True)
            setc(11, _fmt(row["precio_cp"]), True)
            setc(12, _fmt(row["calculado"]), True)
            # Columna 13 editable para ajuste manual
            setc(13, _fmt(row["final"]), True, editable=True)

        self.tbl.resizeColumnsToContents()
        self.tbl.itemChanged.connect(self._on_item_changed)

    def _on_item_changed(self, item):
        """Maneja la edición manual del precio final."""
        if item.column() != 13:
            return

        pk = item.data(Qt.UserRole)
        if not pk:
            return

        try:
            val_txt = item.text().replace("$", "").replace(" ", "").replace(",", ".")
            new_val = float(val_txt)
        except Exception:
            # Si el usuario pone algo inválido, no guardamos (o podríamos revertir)
            return

        # Actualizar en DB (campo precio_manual)
        # Si es 0, asumimos que quiere volver al automático (opcional, pero buena práctica)
        # El requerimiento dice "ajustes manuales", así que guardamos lo que ponga.
        try:
            with AppSession() as s:
                p = s.query(Producto).get(pk)
                if p:
                    p.precio_manual = new_val
                    s.commit()

            # Actualizar modelo en memoria (_rows) para que el próximo recalc lo respete
            # Buscamos la fila correcta
            for r in self._rows:
                if r["pk"] == pk:
                    r["precio_manual"] = new_val
                    # Si puso 0, tal vez quiera recalcular ahora mismo
                    # Pero el _recalc_all se dispara con botón.
                    # Dejamos que el valor visual quede fijo hasta que recalcule.
                    break
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el precio manual: {e}")

    # ------------------------------------------------------------------
    # Context Menu
    # ------------------------------------------------------------------
    def _on_context_menu(self, pos):
        item = self.tbl.itemAt(pos)
        if not item:
            return

        row = item.row()
        pk = self.tbl.item(row, 13).data(Qt.UserRole) # PK is in column 13
        if not pk:
            return

        menu = QMenu(self)

        act_sum = menu.addAction("Sumar monto...")
        act_sub = menu.addAction("Restar monto...")
        menu.addSeparator()
        act_man = menu.addAction("Establecer manual exacto...")
        act_rst = menu.addAction("Revertir a automático")

        action = menu.exec_(self.tbl.mapToGlobal(pos))

        if action == act_sum:
            self._adjust_price(pk, row, factor=1.0)
        elif action == act_sub:
            self._adjust_price(pk, row, factor=-1.0)
        elif action == act_man:
            self._set_manual_exact(pk, row)
        elif action == act_rst:
            self._revert_to_auto(pk, row)

    def _adjust_price(self, pk, row_idx, factor=1.0):
        val, ok = QInputDialog.getDouble(self, "Ajustar precio", "Monto a ajustar:", 0.0, 0.0, 1000000.0, 2)
        if not ok or val == 0:
            return

        current_final = 0.0
        try:
            # Try to get from displayed text in column 13 (Final)
            txt = self.tbl.item(row_idx, 13).text().replace("$", "").replace(" ", "").replace(",", ".")
            current_final = float(txt)
        except:
            pass

        new_val = current_final + (val * factor)
        if new_val < 0: new_val = 0

        self._update_manual_price(pk, new_val)

    def _set_manual_exact(self, pk, row_idx):
        val, ok = QInputDialog.getDouble(self, "Precio Manual", "Nuevo precio final:", 0.0, 0.0, 10000000.0, 2)
        if not ok:
            return
        self._update_manual_price(pk, val)

    def _revert_to_auto(self, pk, row_idx):
        self._update_manual_price(pk, 0.0)

    def _update_manual_price(self, pk, new_val):
        try:
            with AppSession() as s:
                p = s.query(Producto).get(pk)
                if p:
                    p.precio_manual = new_val
                    s.commit()

            # Update local memory
            for r in self._rows:
                if r["pk"] == pk:
                    r["precio_manual"] = new_val
                    # Recalculate only this row logic to update display immediately
                    # Reuse logic from _recalc_all but targeted

                    # NOTE: To simplify, we just trigger _recalc_all or update the single row dict and redisplay.
                    # Since _recalc_all is fast enough for memory update, let's just trigger it or part of it.
                    # But _recalc_all depends on 'denom' which doesn't change by changing manual price of one item.

                    # Let's re-run logic for this row locally to be fast
                    precio_cp = r["precio_cp"] # Base + Prorr (already calc)
                    gan = float(self.sp_gan.value() or 0.0) / 100.0
                    if gan >= 1.0: gan = 0.9999

                    final_raw = precio_cp
                    if (1.0 - gan) > 1e-9:
                         final_raw = precio_cp / (1.0 - gan)

                    if r.get("venta_granel") and r.get("presentacion_cantidad", 1.0) > 0:
                        final_raw = final_raw / r.get("presentacion_cantidad", 1.0)

                    final = float(round(final_raw, -2))
                    if new_val > 0:
                        final = new_val

                    r["final"] = float(round(final, 2))
                    break

            # Refresh UI (only the affected cell really needed, but re-render is safe)
            self._render_table()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo actualizar: {e}")

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    def _on_recalc_clicked(self):
        # guardo la ganancia antes de recalcular (persistencia)
        self._save_gain()
        self._recalc_all()

    def _recalc_all(self):
        # Total de gastos fijos mensual (Costos → Gastos fijos / Sueldos)
        total_fijos = float(total_prorrateable_mes() or 0.0)
        # Formato $X.XXX,YY
        self.lbl_fijos.setText(
            f"Gastos fijos mes: ${total_fijos:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        gan = float(self.sp_gan.value() or 0.0) / 100.0
        if gan >= 1.0:
            gan = 0.9999  # evita división por cero

        # denominador = Σ(+IVA_j * stock_j) de productos con stock>0 y +IVA>0
        denom = 0.0
        for row in self._rows:
            if row["stock"] > 0 and row["mas_iva"] > 0:
                denom += row["mas_iva"] * row["stock"]

        for row in self._rows:
            base_val = 0.0
            # Desactivado prorrateo temporalmente por solicitud del usuario
            # if denom > 0 and row["stock"] > 0 and row["mas_iva"] > 0:
            #     base_val = row["mas_iva"] * row["stock"]
            #     prorr = total_fijos * (base_val / denom)
            # else:
            #     prorr = 0.0
            prorr = 0.0

            precio_cp = row["mas_iva"] + prorr
            if (1.0 - gan) > 1e-9:
                final_raw = precio_cp / (1.0 - gan)
            else:
                final_raw = precio_cp

            # Lógica granel en la tabla
            if row.get("venta_granel") and row.get("presentacion_cantidad", 1.0) > 0:
                final_raw = final_raw / row.get("presentacion_cantidad", 1.0)

            # Guardo el raw calculado
            row["calculado"] = float(round(final_raw, 2))

            # Redondeo a 100
            final = float(round(final_raw, -2))

            # Si hay precio manual (override), usarlo
            manual = float(row.get("precio_manual", 0.0) or 0.0)
            if manual > 0:
                final = manual

            row["prorr"] = float(round(prorr, 2))
            row["precio_cp"] = float(round(precio_cp, 2))
            row["final"] = float(round(final, 2))

        self._render_table()

    # ------------------------------------------------------------------
    # Exportar PDF
    # ------------------------------------------------------------------
    def _export_pdf(self):
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName("precios_barterplus.pdf")
        printer.setOrientation(QPagedPaintDevice.Landscape)
        self.tbl.render(printer)

    # ------------------------------------------------------------------
    # Cableado "Consultar precio" sin romper tu UI
    # ------------------------------------------------------------------
    def _wire_consultar_precio(self):
        """
        Busca un QPushButton hijo (en este tab o ventana) cuyo objectName sea típico
        o cuyo texto contenga 'consult' y 'precio'. No altera la interfaz.
        """
        candidatos_nombres = {"btn_consultar", "btn_consultar_precio", "btnConsultar", "btnConsultarPrecio"}
        btn_obj = None

        # 1) Buscar en este tab
        for b in self.findChildren(QPushButton):
            if b.objectName() in candidatos_nombres:
                btn_obj = b
                break

        # 2) Si no está aquí, buscar en toda la ventana (por texto)
        if btn_obj is None:
            root = self.window() or self
            for b in root.findChildren(QPushButton):
                t = (b.text() or "").strip().lower()
                if ("consult" in t) and ("precio" in t):
                    btn_obj = b
                    break

        if btn_obj is None:
            # No hay botón en esta versión; no hacemos nada.
            return

        try:
            btn_obj.clicked.disconnect()
        except Exception:
            pass
        btn_obj.clicked.connect(lambda: on_consultar_precio_clicked(self))


# ==========================
# CONSULTA: diálogo simple
# ==========================

class _PrecioConsultaDialog(QDialog):
    """
    Muestra solo valores en grande:
      - Siempre 'Precio final'
      - Si hay promo: también 'Precio de promoción'
    """
    def __init__(self, precio_final: float, precio_promo: float | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Consulta de precio")
        lay = QVBoxLayout(self)

        def lbl_big(texto: str, valor: float):
            w = QLabel(f"{texto}\n" + f"${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            f = QFont()
            f.setPointSize(22)
            f.setBold(True)
            w.setFont(f)
            w.setAlignment(Qt.AlignHCenter)
            return w

        # Precio final (siempre)
        lay.addWidget(lbl_big("Precio final", float(precio_final)))

        # Precio de promoción (si existe)
        if precio_promo is not None:
            lay.addWidget(lbl_big("Precio de promoción", float(precio_promo)))

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.button(QDialogButtonBox.Close).setText("Cerrar")
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        lay.addWidget(btns)


# ==========================
# CONSULTA: handler
# ==========================

def _get_selected_producto_id_from_table(tbl) -> int | None:
    """Devuelve el ID del producto desde la fila seleccionada (tolerante)."""
    row = tbl.currentRow() if tbl is not None else -1
    if row < 0:
        return None

    # 1) Columna 'ID' (si fuera numérica)
    try:
        headers = [tbl.horizontalHeaderItem(i).text().strip().lower() for i in range(tbl.columnCount())]
        if "id" in headers:
            c = headers.index("id")
            txt = (tbl.item(row, c).text() or "").strip()
            return int(txt)
    except Exception:
        pass

    # 2) ID en UserRole de la primera celda
    try:
        it = tbl.item(row, 0)
        if it is not None:
            v = it.data(32)  # Qt.UserRole
            if isinstance(v, int):
                return v
    except Exception:
        pass

    # 3) Columna 'Código' → buscar en DB
    try:
        headers = [tbl.horizontalHeaderItem(i).text().strip().lower() for i in range(tbl.columnCount())]
        if "código" in headers or "codigo" in headers:
            c = headers.index("código") if "código" in headers else headers.index("codigo")
            codigo = (tbl.item(row, c).text() or "").strip()
            with SessionLocal() as s:
                p = s.query(Producto).filter(Producto.codigo == codigo).first()
                if p:
                    return p.id
    except Exception:
        pass

    return None


def on_consultar_precio_clicked(self):
    """Solo consulta: NO escribe, NO modifica DB ni la grilla."""
    prod_id = _get_selected_producto_id_from_table(self.tbl)
    if not prod_id:
        QMessageBox.warning(self, "Consultar precio", "Seleccioná un producto en la tabla.")
        return

    with SessionLocal() as s:
        prod = s.query(Producto).get(int(prod_id))
        if not prod:
            QMessageBox.warning(self, "Consultar precio", "No se encontró el producto.")
            return

    try:
        # Precio final "oficial" (con promo si existe) usando las utilidades
        total_mes = tpm_utils()
        base_map  = mapa_stock_valor()
        pf_con_promo, _ = precio_final_sugerido(prod, total_prorrateable=total_mes, base_map=base_map)

        # Calcular precio final base (SIN promo) para poder decidir qué mostrar
        cp, iva_pct, desc_pct = costo_proveedor_iva_descuento(prod)
        A = max(desc_pct, 0.0) / 100.0
        B = max(iva_pct,  0.0) / 100.0
        base_desc = cp - (cp * A)
        neto_iva  = base_desc / max(1.0 - B, 0.0001)
        pro = prorrateo_cuota(prod, total_mes, base_map)
        margen_pct, _ = margen_por_rubro(getattr(prod, "rubro", "") or "")
        C = max(float(margen_pct or 0.0), 0.0) / 100.0
        pf_sin_promo = (neto_iva + pro) / max(1.0 - C, 0.0001)

        # ¿Hay promoción vigente?
        promo = promocion_vigente(prod.id)
        precio_promo = None
        if promo:
            # Si hay promo, pf_con_promo es el precio de promoción
            precio_promo = pf_con_promo
            precio_final  = pf_sin_promo
        else:
            # Sin promo, solo mostramos el final normal
            precio_final  = pf_sin_promo

        dlg = _PrecioConsultaDialog(precio_final=precio_final, precio_promo=precio_promo, parent=self)
        dlg.exec_()

    except Exception as e:
        QMessageBox.critical(self, "Consultar precio", f"Error al calcular: {e}")
2. productos/utils.py
Cambio: En la función prorrateo_cuota, he forzado el retorno a 0.0, desactivando el cálculo que distribuía los costos.

import datetime as dt
from typing import Dict, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func, and_

from db import SessionLocal, ConfigParam, Producto, Stock, Deposito

try:
    from productos.precios.bridge_proveedores import min_costo_proveedor_externo
except Exception:
    min_costo_proveedor_externo = None

try:
    from db.models.proveedores import Proveedor, ProveedorPrecio, ItemListaProveedor, ListaPrecioProveedor
except Exception:
    Proveedor = ProveedorPrecio = ItemListaProveedor = ListaPrecioProveedor = None

try:
    from db.models.costos import ImpuestoPeriodo, GastoNegocio, SueldoLiquidacion
except Exception:
    ImpuestoPeriodo = GastoNegocio = SueldoLiquidacion = None

try:
    from db.models.costos_extra import AdelantoSueldo
except Exception:
    AdelantoSueldo = None

try:
    from db.models.productos import PromocionProducto
except Exception:
    PromocionProducto = None

_DEFAULTS = {
    "margen_baterias": "35.0",
    "margen_lubricantes": "35.0",
    "margen_filtros": "35.0",
    "prorrateo_por": "valor",
    "iva_proveedor_default": "21.0",
    "var_cost_total_mensual": "0.0",
}

def _get_param_map() -> Dict[str, str]:
    with SessionLocal() as s:
        vals = {p.clave: p.valor for p in s.query(ConfigParam).all()}
    for k, v in _DEFAULTS.items(): vals.setdefault(k, v)
    return vals

def get_param_float(key: str, default: float) -> float:
    with SessionLocal() as s:
        row = s.query(ConfigParam).filter(ConfigParam.clave == key).first()
        return float(row.valor) if row and row.valor not in (None, "") else float(default)

def set_param(key: str, value: str):
    with SessionLocal() as s:
        row = s.query(ConfigParam).filter(ConfigParam.clave == key).first()
        if row: row.valor = value
        else:   s.add(ConfigParam(clave=key, valor=value))
        s.commit()

def _month_bounds(d: Optional[dt.date] = None) -> Tuple[dt.date, dt.date]:
    d = d or dt.date.today()
    first = dt.date(d.year, d.month, 1)
    nxt = dt.date(d.year + (1 if d.month == 12 else 0), 1 if d.month == 12 else d.month + 1, 1)
    return first, nxt

def total_prorrateable_mes(ref: Optional[dt.date] = None) -> float:
    def _share_by_periodicity(p: Optional[str]) -> int:
        p = (p or "").upper()
        return 1 if p=='MENSUAL' else 2 if p=='BIMESTRAL' else 3 if p=='TRIMESTRAL' else 12 if p=='ANUAL' else 1
    ini, fin = _month_bounds(ref)
    total = 0.0
    with SessionLocal() as s:
        if ImpuestoPeriodo:
            rows = s.query(ImpuestoPeriodo).filter(and_(ImpuestoPeriodo.fecha_inicio < fin, ImpuestoPeriodo.fecha_fin >= ini)).all()
            for r in rows:
                div = _share_by_periodicity(getattr(r, "periodicidad", None))
                total += float(getattr(r, "monto", 0.0) or 0.0) / max(div, 1)
        if GastoNegocio:
            gns = s.query(GastoNegocio).filter(and_(GastoNegocio.fecha >= ini, GastoNegocio.fecha < fin)).all()
            total += sum(float(g.monto or 0.0) for g in gns)
        if SueldoLiquidacion:
            per = f"{ini.year}-{ini.month:02d}"
            sues = s.query(SueldoLiquidacion).filter(SueldoLiquidacion.periodo_label == per).all()
            total += sum(float(su.neto or 0.0) for su in sues)
        if AdelantoSueldo:
            ads = s.query(AdelantoSueldo).filter(and_(AdelantoSueldo.fecha >= ini, AdelantoSueldo.fecha < fin)).all()
            total += sum(float(a.monto or 0.0) for a in ads)
    return float(round(total, 2))

def _min_precio_proveedor(prod: Producto) -> Tuple[Optional[float], Optional[int], Optional[float]]:
    with SessionLocal() as s:
        if ProveedorPrecio:
            row = s.query(ProveedorPrecio).filter(ProveedorPrecio.producto_id == prod.id).order_by(ProveedorPrecio.precio.asc()).first()
            if row:
                return float(row.precio or 0.0), int(row.proveedor_id or 0), float(getattr(row, "iva_pct", 0.0) or 0.0)
        if ItemListaProveedor and ListaPrecioProveedor:
            row2 = s.query(ItemListaProveedor).filter(ItemListaProveedor.producto_id == prod.id).order_by(ItemListaProveedor.precio.asc()).first()
            if row2:
                prov_id = s.query(ListaPrecioProveedor.proveedor_id).filter(ListaPrecioProveedor.id == row2.lista_id).scalar()
                return float(row2.precio or 0.0), int(prov_id or 0), float(getattr(row2, "iva_pct", 0.0) or 0.0)
    if min_costo_proveedor_externo is not None:
        try:
            costo, prov_id, iva_pct = min_costo_proveedor_externo(prod)
            if costo is not None:
                return float(costo), (int(prov_id) if prov_id else 0), float(iva_pct or 0.0)
        except Exception:
            pass
    return None, None, None

def costo_proveedor_iva_descuento(prod: Producto) -> Tuple[float, float, float]:
    precio, prov_id, iva_linea = _min_precio_proveedor(prod)
    if precio is None:
        precio = float(getattr(prod, "costo", 0.0) or 0.0)
    iva_default = get_param_float("iva_proveedor_default", 21.0)
    iva = iva_linea or iva_default
    desc = 0.0
    if Proveedor and prov_id:
        with SessionLocal() as s:
            prov = s.query(Proveedor).get(int(prov_id))
            if prov:
                if not iva_linea:
                    iva = float(getattr(prov, "iva_pct", iva_default) or iva_default)
                desc = float(getattr(prov, "descuento_pct", 0.0) or 0.0)
    return float(precio), float(iva), float(desc)

def mapa_stock_valor(prorrateo_por: Optional[str] = None) -> Dict[int, float]:
    prorrateo_por = (prorrateo_por or _get_param_map()["prorrateo_por"]).strip().lower()
    with SessionLocal() as s:
        agg = dict(s.query(Stock.producto_id, func.sum(Stock.cantidad)).group_by(Stock.producto_id).all())
        productos = s.query(Producto).all()
    base: Dict[int, float] = {}
    for p in productos:
        cant = float(agg.get(p.id, 0.0) or 0.0)
        if prorrateo_por == "cantidad":
            base[p.id] = cant
        else:
            cp, iva, desc = costo_proveedor_iva_descuento(p)
            base_desc = cp * (1 - desc/100.0)
            neto_iva = base_desc / max(1 - iva/100.0, 0.0001)
            base[p.id] = cant * neto_iva
    return base

def prorrateo_cuota(prod: Producto, total_mes: float, base_map: Dict[int, float]) -> float:
    # Prorrateo desactivado por solicitud
    return 0.0
    # base_total = sum(base_map.values()) or 1.0
    # return float(base_map.get(prod.id, 0.0)) / base_total * float(total_mes or 0.0)

def margen_por_rubro(rubro: str) -> Tuple[float, float]:
    m = _get_param_map()
    r = (rubro or "").lower()
    if r.startswith("bater"):
        return float(m["margen_baterias"]), max(float(m["margen_baterias"]) - 10, 0)
    if r.startswith("lubri"):
        return float(m["margen_lubricantes"]), max(float(m["margen_lubricantes"]) - 10, 0)
    if r.startswith("filt"):
        return float(m["margen_filtros"]), max(float(m["margen_filtros"]) - 10, 0)
    return 35.0, 25.0

def promocion_vigente(prod_id: int, fecha: Optional[dt.date] = None):
    if not PromocionProducto: return None
    fecha = fecha or dt.date.today()
    with SessionLocal() as s:
        return (s.query(PromocionProducto)
                .filter(PromocionProducto.producto_id == prod_id,
                        PromocionProducto.activo == True,
                        PromocionProducto.fecha_inicio <= fecha,
                        PromocionProducto.fecha_fin >= fecha)
                .order_by(PromocionProducto.fecha_inicio.desc())
                .first())

def _round2(v: float) -> float:
    return float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def precio_final_sugerido(prod: Producto, total_prorrateable: Optional[float] = None, base_map: Optional[Dict[int, float]] = None) -> Tuple[float, float]:
    cp, iva_pct, desc_pct = costo_proveedor_iva_descuento(prod)
    if total_prorrateable is None:
        total_prorrateable = total_prorrateable_mes()
    if base_map is None:
        base_map = mapa_stock_valor()
    pro = prorrateo_cuota(prod, total_prorrateable, base_map)
    gan, _ = margen_por_rubro(prod.rubro or "")
    A = max(desc_pct, 0.0) / 100.0
    B = max(iva_pct, 0.0) / 100.0
    C = max(float(gan or 0.0), 0.0) / 100.0
    base_desc = cp - (cp * A)
    neto_iva = base_desc / max(1.0 - B, 0.0001)
    pf = (neto_iva + pro) / max(1.0 - C, 0.0001)

    # Redondeo base a 100
    pf = float(round(pf, -2))

    # Override manual
    try:
        man = float(getattr(prod, "precio_manual", 0.0) or 0.0)
        if man > 0:
            pf = man
    except Exception:
        pass

    promo = promocion_vigente(prod.id)
    if promo:
        t = (getattr(promo, "tipo", "fijo") or "fijo").strip().lower()
        v = float(getattr(promo, "valor", 0.0) or 0.0)
        if t == "fijo": pf = v
        elif t == "porcentaje": pf = pf * (1.0 - max(0.0, min(v, 100.0)) / 100.0)
    pf = _round2(pf)
    return pf, pf
3. ventas/precio_vigente_bridge.py
Cambio: En _precio_final_base, también he forzado prorr = 0.0. Este módulo es usado específicamente por "Nueva Venta" y "Consultar Precio", y estaba calculando el precio inflado de manera independiente. Con este cambio, ambas partes del sistema (Administración de precios y Ventas) usarán la misma lógica sin prorrateo.

# -*- coding: utf-8 -*-
"""
ventas/precio_vigente_bridge.py

Bloque de apoyo: calcula el PRECIO VIGENTE de un producto para Ventas.
Prioridad:
  1) Promoción vigente (valor > 0 y hoy ∈ [inicio, fin]).
     - tipo 'fijo'        => precio = base - valor ($)
     - tipo 'porcentaje'  => precio = base * (1 - valor/100)
  2) Precio Final (Productos→Precios): (mas_iva + prorrateo) / (1 - ganancia)

Uso:
  from ventas.precio_vigente_bridge import calcular_parametros, get_precio_vigente_por_producto
  with SessionLocal() as s:
      params = calcular_parametros(s)      # opcional (mejor rendimiento en listados)
      precio, fuente = get_precio_vigente_por_producto(s, producto, params)
"""

from datetime import date
from typing import Optional, Tuple, Dict

from PyQt5.QtCore import QSettings
from sqlalchemy import or_

from db import SessionLocal, Producto

# Modelo de promociones
from db.models.productos import PromocionProducto

# Utilidades usadas también por Productos→Precios
from productos.listas_bridge import find_price_plus_iva_for_product, get_stock_qty_for_product, enable_cache

from productos.utils import total_prorrateable_mes as _total_prorrateable_mes


def _leer_ganancia_pct() -> float:
    try:
        st = QSettings("BarterPlus", "BarterPlus")
        val = st.value("productos/precios/ganancia_pct", None)
        return float(val) if val is not None else 0.0
    except Exception:
        return 0.0


def _denominador_total(session) -> float:
    denom = 0.0
    for p in session.query(Producto).all():
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
            denom += (mas_iva * stk)
    return denom


def calcular_parametros(session) -> Dict[str, float]:
    """ Calcula una sola vez los parámetros usados por muchos productos. """
    enable_cache()
    total_fijos = float(_total_prorrateable_mes() or 0.0)
    denom_total = _denominador_total(session)
    ganancia_pct = _leer_ganancia_pct()
    return {"total_fijos": total_fijos, "denom_total": denom_total, "ganancia_pct": ganancia_pct}


def _precio_final_base(p: Producto, total_fijos: float, denom_total: float, ganancia_pct: float) -> float:
    """ Precio Final (el de Productos→Precios, sin promo). """
    try:
        info = find_price_plus_iva_for_product(p) or {}
        mas_iva = float(info.get("mas_iva", 0.0)) if isinstance(info, dict) else float(info or 0.0)
    except Exception:
        mas_iva = 0.0
    try:
        stk = float(get_stock_qty_for_product(p) or 0.0)
    except Exception:
        stk = 0.0

    # Desactivado prorrateo temporalmente por solicitud
    # prorr = 0.0
    # if denom_total > 0 and mas_iva > 0 and stk > 0:
    #     prorr = total_fijos * ((mas_iva * stk) / denom_total)
    prorr = 0.0

    precio_cp = mas_iva + prorr
    gan = max(0.0, min(500.0, float(ganancia_pct))) / 100.0

    # Precio final por presentación completa
    final_full = float(precio_cp / (1.0 - gan)) if (1.0 - gan) > 1e-9 else float(precio_cp)

    # Si es venta a granel, dividir por la presentación
    # (ej: precio de tambor 200L -> precio por litro)
    try:
        is_granel = False
        if hasattr(p, "venta_granel"):
            is_granel = bool(getattr(p, "venta_granel") in (1, True, "1"))

        if is_granel:
            qty = 1.0
            if hasattr(p, "presentacion_cantidad"):
                qty = float(getattr(p, "presentacion_cantidad") or 1.0)
            if qty > 0:
                final_full = final_full / qty
    except Exception:
        pass

    # Redondeo a 100
    final_full = float(round(final_full, -2))

    # Manual override (Precio manual fijo)
    try:
        man = float(getattr(p, "precio_manual", 0.0) or 0.0)
        if man > 0:
            final_full = man
    except Exception:
        pass

    # Fallback si el precio calculado es 0 (para productos sin lista)
    if final_full == 0:
        for fname in ("precio_minorista", "precio_venta", "precio"):
            try:
                val = float(getattr(p, fname, 0.0) or 0.0)
                if val > 0:
                    final_full = val
                    break
            except Exception:
                pass

    return final_full


def _precio_promo_vigente(session, p: Producto, base_final: float) -> Optional[float]:
    """ Devuelve precio PROMO vigente para p, o None si no hay. """
    if PromocionProducto is None:
        return None
    hoy = date.today()
    pr = (session.query(PromocionProducto)
          .filter(PromocionProducto.producto_id == p.id)
          .filter(PromocionProducto.valor > 0)
          .filter(PromocionProducto.fecha_inicio <= hoy)
          .filter(PromocionProducto.fecha_fin >= hoy)
          .order_by(PromocionProducto.fecha_inicio.desc())
          .first())
    if not pr:
        return None

    try:
        if pr.tipo == "porcentaje":
            pct = max(0.0, min(float(pr.valor or 0.0), 100.0)) / 100.0
            return max(0.0, base_final * (1.0 - pct))
        desc = max(0.0, float(pr.valor or 0.0))
        return max(0.0, base_final - desc)
    except Exception:
        return None


def get_precio_vigente_por_producto(session, p: Producto, params: Dict[str, float] = None) -> Tuple[float, str]:
    """ Retorna (precio_vigente, fuente) donde fuente ∈ {'PROMO','PRECIOS'} """
    if params is None:
        params = calcular_parametros(session)
    base = _precio_final_base(p, params["total_fijos"], params["denom_total"], params["ganancia_pct"])
    promo = _precio_promo_vigente(session, p, base)
    if promo is not None:
        return float(round(promo, 2)), "PROMO"
    return float(round(base, 2)), "PRECIOS"


def get_precio_vigente_por_barcode(session, barcode: str, params: Dict[str, float] = None):
    """ Busca por código de barras y retorna (precio, fuente, producto_id) o None. """
    if not barcode:
        return None
    conds = []
    for cname in ("codigo_barras", "barcode", "cb", "ean", "codigo_barra", "cod_barra"):
        col = getattr(Producto, cname, None)
        if col is not None:
            conds.append(col == barcode)
    if not conds:
        return None

    p = session.query(Producto).filter(or_(*conds)).first()
    if not p:
        return None

    precio, fuente = get_precio_vigente_por_producto(session, p, params)
    return precio, fuente, int(getattr(p, "id", 0))