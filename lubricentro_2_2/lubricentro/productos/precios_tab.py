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
    QDialog, QDialogButtonBox, QMessageBox, QMenu, QInputDialog,
    QComboBox, QCheckBox
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

        # Filtros
        self.lay_filtros = QHBoxLayout()
        self.cmb_marca = QComboBox()
        self.cmb_rubro = QComboBox()
        self.cmb_subrubro = QComboBox()
        self.chk_recientes = QCheckBox("Agregados hoy")

        self.lay_filtros.addWidget(QLabel("Marca:"))
        self.lay_filtros.addWidget(self.cmb_marca)
        self.lay_filtros.addWidget(QLabel("Rubro:"))
        self.lay_filtros.addWidget(self.cmb_rubro)
        self.lay_filtros.addWidget(QLabel("Subrubro:"))
        self.lay_filtros.addWidget(self.cmb_subrubro)
        self.lay_filtros.addWidget(self.chk_recientes)
        self.lay_filtros.addStretch()

        lay.addLayout(self.lay_filtros)

        self.cmb_marca.currentIndexChanged.connect(self._aplicar_filtros)
        self.cmb_rubro.currentIndexChanged.connect(self._aplicar_filtros)
        self.cmb_subrubro.currentIndexChanged.connect(self._aplicar_filtros)
        self.chk_recientes.stateChanged.connect(self._aplicar_filtros)


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
                "rubro": str(getattr(p, "rubro", "") or ""),
                "subrubro": str(getattr(p, "subrubro", "") or ""),
                "creado_en": getattr(p, "creado_en", None),

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
        self._actualizar_combos_filtro()



    def _actualizar_combos_filtro(self):
        m_marca = self.cmb_marca.currentText()
        m_rubro = self.cmb_rubro.currentText()
        m_subrubro = self.cmb_subrubro.currentText()

        self.cmb_marca.blockSignals(True)
        self.cmb_rubro.blockSignals(True)
        self.cmb_subrubro.blockSignals(True)

        self.cmb_marca.clear()
        self.cmb_rubro.clear()
        self.cmb_subrubro.clear()

        marcas = sorted(list(set([r["marca"] for r in self._rows if r.get("marca")])))
        rubros = sorted(list(set([r.get("rubro", "") for r in self._rows if r.get("rubro")])))
        subrubros = sorted(list(set([r.get("subrubro", "") for r in self._rows if r.get("subrubro")])))

        self.cmb_marca.addItem("Todas")
        self.cmb_marca.addItems(marcas)
        self.cmb_rubro.addItem("Todos")
        self.cmb_rubro.addItems(rubros)
        self.cmb_subrubro.addItem("Todos")
        self.cmb_subrubro.addItems(subrubros)

        idx = self.cmb_marca.findText(m_marca)
        if idx >= 0: self.cmb_marca.setCurrentIndex(idx)
        idx = self.cmb_rubro.findText(m_rubro)
        if idx >= 0: self.cmb_rubro.setCurrentIndex(idx)
        idx = self.cmb_subrubro.findText(m_subrubro)
        if idx >= 0: self.cmb_subrubro.setCurrentIndex(idx)

        self.cmb_marca.blockSignals(False)
        self.cmb_rubro.blockSignals(False)
        self.cmb_subrubro.blockSignals(False)

        self._aplicar_filtros()

    def _aplicar_filtros(self):
        if not hasattr(self, '_rows'): return

        f_marca = self.cmb_marca.currentText()
        f_rubro = self.cmb_rubro.currentText()
        f_subrubro = self.cmb_subrubro.currentText()
        f_reciente = self.chk_recientes.isChecked()

        import datetime
        hoy = datetime.datetime.now().date()

        for i, r in enumerate(self._rows):
            mostrar = True
            if f_marca != "Todas" and f_marca != "" and r.get("marca", "") != f_marca: mostrar = False
            if f_rubro != "Todos" and f_rubro != "" and r.get("rubro", "") != f_rubro: mostrar = False
            if f_subrubro != "Todos" and f_subrubro != "" and r.get("subrubro", "") != f_subrubro: mostrar = False
            if f_reciente:
                if r.get("creado_en") is None or r.get("creado_en").date() != hoy: mostrar = False

            self.tbl.setRowHidden(i, not mostrar)

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
