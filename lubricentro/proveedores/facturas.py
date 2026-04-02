# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QDateEdit, QDoubleSpinBox, QSpinBox,
    QComboBox, QPushButton, QMessageBox, QGroupBox, QGridLayout,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QDialog
)
from PyQt5.QtCore import QDate, Qt
from datetime import datetime, date

# Bootstrap modelos proveedores
from proveedores.bootstrap import bootstrap
_ns = bootstrap()
ProvSession = _ns["SessionLocal"]
Proveedor = _ns.get("Proveedor") or _ns.get("Proveedores")
MovimientoProveedor = _ns.get("MovimientoProveedor") or _ns.get("MovProveedor")
FacturaProveedor = _ns.get("FacturaProveedor")
FacturaItem = _ns.get("FacturaItem")
ItemListaProveedor = _ns.get("ItemListaProveedor")

# Modelos Main DB (Stock)
from db import SessionLocal as MainSession, Producto, Stock as StockModel
from services.producto_service import ProductoService
from productos.listas_bridge import find_price_plus_iva_for_product

class FacturaProveedorWidget(QWidget):
    """
    Carga de Facturas/Remitos/Pagos de Proveedores.
    Ahora soporta items detallados e impacto en stock (Facturas/Remitos).
    """
    def __init__(self, on_after_save=None, parent=None):
        super().__init__(parent)
        self._on_after_save = on_after_save
        self._items = [] # List of tuples/dicts: (code, desc, qty, price, subtotal, pid_main, is_new)
        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- Header Form ---
        form = QFormLayout()

        # Proveedor
        self.cb_prov = QComboBox()
        self.cb_prov.currentIndexChanged.connect(self._on_prov_changed)
        self._cargar_proveedores()
        form.addRow("Proveedor:", self.cb_prov)

        # Tipo
        self.cb_tipo = QComboBox()
        self.cb_tipo.addItems(["Factura", "Remito", "Pago"])
        form.addRow("Tipo:", self.cb_tipo)

        # Número
        self.txt_numero = QLineEdit()
        form.addRow("Número:", self.txt_numero)

        # Fecha emisión
        self.dt_fecha = QDateEdit()
        self.dt_fecha.setCalendarPopup(True)
        self.dt_fecha.setDate(QDate.currentDate())
        form.addRow("Fecha emisión:", self.dt_fecha)

        # Días de crédito -> vencimiento
        self.spn_dias = QSpinBox()
        self.spn_dias.setRange(0, 365)
        self.spn_dias.setValue(0)
        self.spn_dias.valueChanged.connect(self._recalcular_vto)
        form.addRow("Días de crédito:", self.spn_dias)

        # Vencimiento (solo lectura)
        self.dt_vto = QDateEdit()
        self.dt_vto.setCalendarPopup(True)
        self.dt_vto.setDate(QDate.currentDate())
        self.dt_vto.setReadOnly(True)
        form.addRow("Fecha vencimiento:", self.dt_vto)

        root.addLayout(form)

        # --- Items Section (Visible only for Factura/Remito) ---
        self.grp_items = QGroupBox("Detalle de Ítems (Impacta Stock)")
        l_items = QVBoxLayout(self.grp_items)

        # Search Bar
        h_search = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Buscar producto (Código o Nombre)...")
        self.txt_search.returnPressed.connect(self._buscar_producto)
        btn_search = QPushButton("Buscar / Agregar")
        btn_search.clicked.connect(self._buscar_producto)
        h_search.addWidget(self.txt_search)
        h_search.addWidget(btn_search)
        l_items.addLayout(h_search)

        # Table
        self.tbl_items = QTableWidget()
        self.tbl_items.setColumnCount(6)
        self.tbl_items.setHorizontalHeaderLabels(["Código", "Descripción", "Cant.", "Precio Unit.", "Subtotal", "Estado"])
        self.tbl_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_items.itemChanged.connect(self._on_item_changed)
        l_items.addWidget(self.tbl_items)

        # Total Label
        self.lbl_total_items = QLabel("Total: $0.00")
        self.lbl_total_items.setStyleSheet("font-size: 14px; font-weight: bold;")
        l_items.addWidget(self.lbl_total_items, alignment=Qt.AlignRight)

        root.addWidget(self.grp_items)

        # --- Simple Amount (Visible mainly for consistency check or manual override?) ---
        # NOTE: For Factura/Remito, Total is calculated from items.
        # But we might want to allow manual total if they don't enter items.
        # Let's keep spn_monto but make it update from table, yet editable.

        form_bottom = QFormLayout()
        self.spn_monto = QDoubleSpinBox()
        self.spn_monto.setRange(0.00, 1_000_000_000.00)
        self.spn_monto.setDecimals(2)
        form_bottom.addRow("Monto Total Documento:", self.spn_monto)

        # Descripción libre
        self.txt_desc = QTextEdit()
        self.txt_desc.setPlaceholderText("Descripción / observaciones")
        self.txt_desc.setMaximumHeight(60)
        form_bottom.addRow("Descripción:", self.txt_desc)
        root.addLayout(form_bottom)

        # --- Payment Methods (Visible only for 'Pago') ---
        self.grp_pago = QGroupBox("Formas de pago")
        grid = QGridLayout(self.grp_pago)

        self.spn_pago_efec   = QDoubleSpinBox(); self._cfg_pago(self.spn_pago_efec)
        self.spn_pago_transf = QDoubleSpinBox(); self._cfg_pago(self.spn_pago_transf)
        self.spn_pago_cheq   = QDoubleSpinBox(); self._cfg_pago(self.spn_pago_cheq)
        self.spn_pago_bat    = QDoubleSpinBox(); self._cfg_pago(self.spn_pago_bat)
        self.spn_pago_otro   = QDoubleSpinBox(); self._cfg_pago(self.spn_pago_otro)

        grid.addWidget(QLabel("Efectivo:"),       0, 0); grid.addWidget(self.spn_pago_efec,   0, 1)
        grid.addWidget(QLabel("Transferencia:"),  1, 0); grid.addWidget(self.spn_pago_transf, 1, 1)
        grid.addWidget(QLabel("Cheque:"),         2, 0); grid.addWidget(self.spn_pago_cheq,   2, 1)
        grid.addWidget(QLabel("Batería usada:"),  3, 0); grid.addWidget(self.spn_pago_bat,    3, 1)
        grid.addWidget(QLabel("Otro:"),           4, 0); grid.addWidget(self.spn_pago_otro,   4, 1)

        root.addWidget(self.grp_pago)

        self.cb_tipo.currentTextChanged.connect(self._toggle_pago_panel)
        self._toggle_pago_panel(self.cb_tipo.currentText())

        # Guardar
        btns = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar Confirmar Stock")
        self.btn_guardar.clicked.connect(self._guardar_inline)
        btns.addWidget(self.btn_guardar)
        root.addLayout(btns)

        self._recalcular_vto()

    def _cfg_pago(self, spn: QDoubleSpinBox):
        spn.setRange(0.0, 1_000_000_000.0)
        spn.setDecimals(2)

    def _toggle_pago_panel(self, tipo: str):
        is_pago = (tipo == "Pago")
        self.grp_pago.setVisible(is_pago)
        self.grp_items.setVisible(not is_pago)
        # self.spn_monto.setEnabled(not is_pago) # Allow manual edit even for Items mode to adjust cents? Yes.

    def _recalcular_vto(self):
        try:
            base = self._to_pydate(self.dt_fecha)
            dias = int(self.spn_dias.value() or 0)
            vto = base.toordinal() + dias
            d = date.fromordinal(vto)
            self.dt_vto.setDate(QDate(d.year, d.month, d.day))
        except Exception:
            self.dt_vto.setDate(self.dt_fecha.date())

    def _on_prov_changed(self):
        # Clear items when provider changes? Maybe warn.
        if self.tbl_items.rowCount() > 0:
            # Optional warning
            QMessageBox.information(self, "OK", "Guardado y stock actualizado.")

    # ---------------- Helper Methods for External Edit/Delete ----------------
    def _cargar_factura_para_edicion(self, fid):
        with ProvSession() as s:
            f = s.query(FacturaProveedor).get(fid)
            if not f: return

            # Load Header
            self.txt_numero.setText(f.numero or "")
            self.cb_tipo.setCurrentText(f.tipo or "Factura")
            if f.fecha:
                self.dt_fecha.setDate(QDate(f.fecha.year, f.fecha.month, f.fecha.day))
            if f.fecha_vencimiento:
                self.dt_vto.setDate(QDate(f.fecha_vencimiento.year, f.fecha_vencimiento.month, f.fecha_vencimiento.day))
            self.spn_dias.setValue(f.plazo_dias or 0)
            self.spn_monto.setValue(f.monto_total or 0.0)
            self.txt_desc.setText(f.descripcion or "")

            # Load Items
            items = s.query(FacturaItem).filter(FacturaItem.factura_id == fid).all()
            self.tbl_items.setRowCount(0)
            for it in items:
                r = self.tbl_items.rowCount()
                self.tbl_items.insertRow(r)
                self.tbl_items.setItem(r, 0, QTableWidgetItem(it.codigo or ""))
                self.tbl_items.setItem(r, 1, QTableWidgetItem(it.descripcion or ""))

                it_qty = QTableWidgetItem(f"{it.cantidad or 0:.2f}")
                it_qty.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                self.tbl_items.setItem(r, 2, it_qty)

                it_pr = QTableWidgetItem(f"{it.precio_unitario or 0:.2f}")
                it_pr.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                self.tbl_items.setItem(r, 3, it_pr)

                it_sub = QTableWidgetItem(f"{it.subtotal or 0:.2f}")
                it_sub.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.tbl_items.setItem(r, 4, it_sub)

                pid_txt = f"ID: {it.producto_id}" if it.producto_id else "LINK?"
                it_st = QTableWidgetItem(pid_txt)
                it_st.setData(Qt.UserRole, it.producto_id)
                self.tbl_items.setItem(r, 5, it_st)

            self._recalc_totals()

            # Store ID for update
            self.setProperty("current_factura_id", fid)
            self.btn_guardar.setText("Actualizar Factura (Revertir+Guardar)")
            QMessageBox.information(self, "Modificar", f"Factura {f.numero} cargada. Al guardar se revertirá el stock anterior y aplicará el nuevo.")

    def _borrar_factura(self, fid):
        resp = QMessageBox.question(self, "Borrar", "¿Eliminar esta factura y revertir el stock?", QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes: return

        try:
            self._revertir_stock_y_movimientos(fid)

            # Delete Record
            with ProvSession() as s:
                f = s.query(FacturaProveedor).get(fid)
                if f:
                    s.query(FacturaItem).filter(FacturaItem.factura_id == fid).delete()
                    s.delete(f)
                    s.commit()

            QMessageBox.information(self, "Borrado", "Factura eliminada y stock revertido.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo borrar: {e}")

    def _revertir_stock_y_movimientos(self, fid):
        # 1. Get Items to revert stock
        items_to_revert = []

        with ProvSession() as s:
            f = s.query(FacturaProveedor).get(fid)
            if not f: return

            # Items
            its = s.query(FacturaItem).filter(FacturaItem.factura_id == fid).all()
            for it in its:
                if it.producto_id and it.cantidad:
                    items_to_revert.append({"pid": it.producto_id, "qty": it.cantidad})

            # Find and Delete Movement
            m = s.query(MovimientoProveedor).filter(
                MovimientoProveedor.proveedor_id == f.proveedor_id,
                MovimientoProveedor.fecha == f.fecha,
                MovimientoProveedor.debe == f.monto_total
            ).first()
            if m:
                s.delete(m)
            s.commit() # Commit mov deletion

        # 2. Revert Stock in Main DB
        if items_to_revert:
            with MainSession() as ms:
                for item in items_to_revert:
                    pid = item["pid"]
                    # Calculate bulk reversal
                    qty_revert = item["qty"]

                    prod_obj = ms.query(Producto).get(pid)
                    if prod_obj:
                        is_granel = False
                        try:
                            if hasattr(prod_obj, "venta_granel") and (prod_obj.venta_granel in (1, True, "1")):
                                is_granel = True
                        except: QMessageBox.information(self, "OK", "Guardado y stock actualizado.")

                        if is_granel:
                            pres = 1.0
                            try:
                                if hasattr(prod_obj, "presentacion_cantidad"):
                                    pres = float(prod_obj.presentacion_cantidad or 1.0)
                            except: QMessageBox.information(self, "OK", "Guardado y stock actualizado.")
                            if pres > 0:
                                qty_revert = item["qty"] * pres

                    stk = ms.query(StockModel).filter(StockModel.producto_id == pid, StockModel.deposito_id == 1).first()
                    if stk:
                        stk.cantidad -= qty_revert # Decrease stock
                ms.commit()

    # ---------------- Datos ----------------
    def _cargar_proveedores(self):
        self.cb_prov.blockSignals(True)
        try:
            if Proveedor is None:
                return
            with ProvSession() as s:
                nombre_col = getattr(Proveedor, "nombre", None) or getattr(Proveedor, "razon_social", None)
                q = s.query(Proveedor)
                if nombre_col is not None:
                    q = q.order_by(nombre_col.asc())
                for p in q.all():
                    nombre = getattr(p, "nombre", None) or getattr(p, "razon_social", "") or ""
                    self.cb_prov.addItem(str(nombre), int(getattr(p, "id", 0) or 0))
        except Exception as e:
            print(f"Factura: error cargando proveedores: {e}")
        finally:
            self.cb_prov.blockSignals(False)

    # ---------------- Item Logic ----------------
    def _buscar_producto(self):
        txt = self.txt_search.text().strip()
        if not txt: return

        prov_id = self.cb_prov.currentData()
        if not prov_id and self.cb_tipo.currentText() != "Pago":
            pass
            return

        # 1. Search in Main DB (Stock)
        found_main = []
        with MainSession() as s:
            # Try exact code
            q = s.query(Producto).filter(
                (Producto.codigo_barras == txt) | (Producto.sku == txt) | (Producto.codigo_proveedor == txt)
            )
            found_main = q.all()
            if not found_main:
                # Try name like
                q = s.query(Producto).filter(Producto.nombre.ilike(f"%{txt}%"))
                found_main = q.all()

        # 2. Search in Provider List (Prov DB)
        found_list = []
        if prov_id and ItemListaProveedor:
            with ProvSession() as s:
                # Join with Lista to filter by provider? assuming logic handles it via lista_id or we filter later
                # Currently ItemListaProveedor has lista_id. We need lists for this provider.
                # Simplified: Search items where list belongs to provider.
                # Assuming bootstrap logic is correct.
                # We do a join or subquery.
                from sqlalchemy import select
                stmt = select(ItemListaProveedor).join(bootstrap()["ListaPrecioProveedor"]).where(
                    bootstrap()["ListaPrecioProveedor"].proveedor_id == prov_id,
                    (ItemListaProveedor.producto_codigo == txt) | (ItemListaProveedor.descripcion.ilike(f"%{txt}%"))
                )
                found_list = s.execute(stmt).scalars().all()

        # If exactly one result in main, use it.
        # But we prefer checking list for price.
        # Let's show a picker if mixed results.
        if len(found_main) == 1 and len(found_list) == 0:
            self._agregar_item_desde_seleccion({"type": "main", "obj": found_main[0]})
            return
        elif len(found_list) == 1 and len(found_main) == 0:
            self._agregar_item_desde_seleccion({"type": "list", "obj": found_list[0]})
            return

        # Resolution Dialog if multiple or none
        if not found_main and not found_list:
            # Offer to create NEW
            resp = QMessageBox.question(self, "Nuevo", f"No se encontró '{txt}'. ¿Crear producto nuevo?", QMessageBox.Yes | QMessageBox.No)
            if resp == QMessageBox.Yes:
                self._crear_producto_nuevo(txt)
            return

        self._mostrar_selector_productos(found_main, found_list)

    def _mostrar_selector_productos(self, main_prods, list_items):
        # Dialog with table to select
        dlg = QDialog(self)
        dlg.setWindowTitle("Seleccionar Producto")
        dlg.resize(700, 400)
        lay = QVBoxLayout(dlg)

        tbl = QTableWidget()
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels(["Fuente", "Código", "Descripción", "Precio Lista", "ID Ref"])
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        lay.addWidget(tbl)

        # Fill
        # Main DB products
        for p in main_prods:
            r = tbl.rowCount(); tbl.insertRow(r)
            tbl.setItem(r, 0, QTableWidgetItem("Stock Local"))
            tbl.setItem(r, 1, QTableWidgetItem(str(p.codigo_barras or p.sku or "")))
            tbl.setItem(r, 2, QTableWidgetItem(str(p.nombre)))
            # Price? Maybe cost
            costo = getattr(p, "costo", 0.0)
            tbl.setItem(r, 3, QTableWidgetItem(f"{costo:.2f}"))
            tbl.item(r, 0).setData(Qt.UserRole, {"type": "main", "obj": p})

        # List items
        for it in list_items:
            r = tbl.rowCount(); tbl.insertRow(r)
            tbl.setItem(r, 0, QTableWidgetItem("Lista Prov."))
            tbl.setItem(r, 1, QTableWidgetItem(str(it.producto_codigo)))
            tbl.setItem(r, 2, QTableWidgetItem(str(it.descripcion)))
            tbl.setItem(r, 3, QTableWidgetItem(f"{it.precio:.2f}"))
            tbl.item(r, 0).setData(Qt.UserRole, {"type": "list", "obj": it})

        def _select():
            row = tbl.currentRow()
            if row >= 0:
                data = tbl.item(row, 0).data(Qt.UserRole)
                self._agregar_item_desde_seleccion(data)
                dlg.accept()

        btn = QPushButton("Seleccionar")
        btn.clicked.connect(_select)
        tbl.cellDoubleClicked.connect(_select)
        lay.addWidget(btn)

        dlg.exec_()

    def _crear_producto_nuevo(self, search_txt):
        # Open Editor
        from productos.edicion import ProductoEditorDialog
        dlg = ProductoEditorDialog(parent=self)
        # Pre-fill
        dlg.inp_nombre.setText(search_txt)
        # Set Provider
        current_prov_id = self.cb_prov.currentData()
        if current_prov_id:
            idx = -1
            for i in range(dlg.cmb_prov.count()):
                if dlg.cmb_prov.itemData(i) == current_prov_id:
                    idx = i; break
            if idx >= 0: dlg.cmb_prov.setCurrentIndex(idx)

        if dlg.exec_() == QDialog.Accepted:
            # Need to get the created product ID
            # ProductoEditorDialog saves to DB.
            # We can find it. Or modify Editor to return it.
            # Assuming Editor saved it, we assume user can search again or we try to find it.
            # Let's search again automatically.
            self.txt_search.setText(dlg.inp_nombre.text())
            self._buscar_producto()

    def _agregar_item_desde_seleccion(self, data):
        # Determine fields
        pid_main = None
        code = ""
        desc = ""
        price = 0.0

        if data["type"] == "main":
            # Existing stock product
            # Use logic to fetch price from provider list if possible, else cost
            p_obj_main = data["obj"] # This is detached session object, careful
            pid_main = p_obj_main.id
            code = p_obj_main.codigo_barras or p_obj_main.sku or ""
            desc = p_obj_main.nombre

            # Try to find list price for this product
            # We need a fresh session or use the helper
            with MainSession() as s:
               p_fresh = s.query(Producto).get(pid_main)
               info = find_price_plus_iva_for_product(p_fresh)
               if info["ok"] and info["base"] > 0:
                   price = info["base"] # Costo lista
               else:
                   price = getattr(p_fresh, "costo", 0.0) or 0.0

        elif data["type"] == "list":
            # From list. Check if linked to stock?
            # Ideally we check if this code exists in main DB.
            # For now, treat as "Potential New" if not matched,
            # OR ask to link.
            # Simplification: If from List, we assume we might need to create it OR it wasn't found by code in Main.
            # We add it to the grid. If user saves, and no PID, we create it.
            it = data["obj"]
            code = it.producto_codigo
            desc = it.descripcion
            price = it.precio
            # Try to see if this code matches a product in main (maybe search failed due to fuzzy?)
            # Re-check main DB by code
            with MainSession() as s:
                p = s.query(Producto).filter(Producto.codigo_proveedor == code).first()
                if p:
                    pid_main = p.id
                    # Update desc from main? Keep list desc?
                    # Keep list desc for invoice
                else:
                    # New product to be created
                    QMessageBox.information(self, "OK", "Guardado y stock actualizado.")

        # Add to table
        row = self.tbl_items.rowCount()
        self.tbl_items.insertRow(row)

        # Code
        self.tbl_items.setItem(row, 0, QTableWidgetItem(str(code)))
        # Desc
        self.tbl_items.setItem(row, 1, QTableWidgetItem(str(desc)))
        # Qty (Editable)
        it_qty = QTableWidgetItem("1.00")
        it_qty.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
        self.tbl_items.setItem(row, 2, it_qty)
        # Price (Editable)
        it_pr = QTableWidgetItem(f"{price:.2f}")
        it_pr.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
        self.tbl_items.setItem(row, 3, it_pr)
        # Subtotal
        it_sub = QTableWidgetItem(f"{price:.2f}")
        it_sub.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable) # Calc
        self.tbl_items.setItem(row, 4, it_sub)
        # State/PID
        state_txt = f"ID: {pid_main}" if pid_main else "NUEVO"
        it_st = QTableWidgetItem(state_txt)
        it_st.setData(Qt.UserRole, pid_main) # Store PID
        self.tbl_items.setItem(row, 5, it_st)

        self._recalc_totals()
        self.txt_search.clear()
        self.txt_search.setFocus()

    def _on_item_changed(self, item):
        col = item.column()
        row = item.row()
        if col in (2, 3): # Qty or Price changed
            try:
                q = float(self.tbl_items.item(row, 2).text().replace(",", "."))
                p = float(self.tbl_items.item(row, 3).text().replace(",", "."))
                sub = q * p
                self.tbl_items.item(row, 4).setText(f"{sub:.2f}")
                self._recalc_totals()
            except: QMessageBox.information(self, "OK", "Guardado y stock actualizado.")

    def _recalc_totals(self):
        total = 0.0
        for r in range(self.tbl_items.rowCount()):
            try:
                sub = float(self.tbl_items.item(r, 4).text().replace(",", "."))
                total += sub
            except: QMessageBox.information(self, "OK", "Guardado y stock actualizado.")
        self.lbl_total_items.setText(f"Total: ${total:,.2f}")
        self.spn_monto.setValue(total)

    # ---------------- Guardado ----------------
    def _guardar_inline(self):
        try:
            # Check if updating
            current_fid = self.property("current_factura_id")

            if current_fid:
                # Revert old impacts BEFORE saving new state
                self._revertir_stock_y_movimientos(current_fid)
                # Cleanup old records (simple strategy: delete old items and header, re-create)
                with ProvSession() as s:
                    f = s.query(FacturaProveedor).get(current_fid)
                    if f:
                        s.query(FacturaItem).filter(FacturaItem.factura_id == current_fid).delete()
                        s.delete(f)
                        s.commit()

            # --- Continue with standard Save logic ---
            prov_id = int(self.cb_prov.currentData() or 0)
            if not prov_id:
                pass
                return

            tipo     = self.cb_tipo.currentText()
            numero   = (self.txt_numero.text() or "").strip()
            fecha    = self._to_pydate(self.dt_fecha)
            vto      = self._to_pydate(self.dt_vto)
            desc     = (self.txt_desc.toPlainText() or "").strip()
            prov_nom = self.cb_prov.currentText().strip()

            comp_str = "Factura" if tipo == "Factura" else ("Remito" if tipo == "Remito" else "Pago")
            descripcion_mov = f"[{prov_nom}] {comp_str} {numero} {desc}".strip()

            # 1. Validate Items if Factura/Remito
            items_data = []
            if tipo in ("Factura", "Remito"):
                if self.tbl_items.rowCount() == 0:
                    QMessageBox.warning(self, "Items", "Debe agregar ítems a la factura.")
                    return
                for r in range(self.tbl_items.rowCount()):
                    code = self.tbl_items.item(r, 0).text()
                    dscr = self.tbl_items.item(r, 1).text()
                    qty = float(self.tbl_items.item(r, 2).text().replace(",", "."))
                    prc = float(self.tbl_items.item(r, 3).text().replace(",", "."))
                    pid = self.tbl_items.item(r, 5).data(Qt.UserRole)
                    if qty <= 0:
                        QMessageBox.warning(self, "Items", f"Cantidad inválida en fila {r+1}")
                        return
                    items_data.append({
                        "code": code, "desc": dscr, "qty": qty, "price": prc, "pid": pid
                    })

            # 2. Save Header & Mov in Prov DB
            with ProvSession() as s:
                factura_id = None
                if tipo in ("Factura", "Remito"):
                    monto_doc = float(self.spn_monto.value() or 0.0)

                    # Create Factura Header
                    fac = FacturaProveedor(
                        proveedor_id=prov_id,
                        numero=numero,
                        tipo=tipo,
                        fecha=fecha,
                        plazo_dias=self.spn_dias.value(),
                        fecha_vencimiento=vto,
                        monto_total=monto_doc,
                        estado="Pendiente",
                        descripcion=desc
                    )
                    s.add(fac)
                    s.flush() # get ID
                    factura_id = fac.id

                    # Items
                    for it in items_data:
                        fi = FacturaItem(
                            factura_id=factura_id,
                            producto_id=it["pid"], # Null if new
                            codigo=it["code"],
                            descripcion=it["desc"],
                            cantidad=it["qty"],
                            precio_unitario=it["price"],
                            subtotal=it["qty"]*it["price"]
                        )
                        s.add(fi)

                    # Financial Mov
                    mov = MovimientoProveedor(
                        proveedor_id=prov_id,
                        fecha=fecha,
                        fecha_vencimiento=vto,
                        descripcion=descripcion_mov,
                        forma_pago="",
                        debe=monto_doc,
                        haber=0.0
                    )
                    s.add(mov)
                else:
                    # Pago logic (unchanged mostly)
                    total_pago = (
                        float(self.spn_pago_efec.value() or 0.0) +
                        float(self.spn_pago_transf.value() or 0.0) +
                        float(self.spn_pago_cheq.value() or 0.0) +
                        float(self.spn_pago_bat.value() or 0.0) +
                        float(self.spn_pago_otro.value() or 0.0)
                    )
                    if total_pago <= 0:
                        QMessageBox.warning(self, "Pago", "El total del pago debe ser mayor a 0.")
                        return
                    mov = MovimientoProveedor(
                        proveedor_id=prov_id,
                        fecha=fecha,
                        fecha_vencimiento=None,
                        descripcion=descripcion_mov,
                        forma_pago="Multipago",
                        debe=0.0,
                        haber=total_pago
                    )
                    s.add(mov)

                s.commit()

            # 3. Update Main DB (Stock & Create Products)
            if tipo in ("Factura", "Remito"):
                with MainSession() as ms:
                    for it in items_data:
                        pid = it["pid"]

                        # If New (no PID), create product
                        if not pid:
                            new_prod = Producto(
                                nombre=it["desc"],
                                codigo_proveedor=it["code"],
                                proveedor_id=prov_id,
                                costo=it["price"],
                                iva=21.0, # Default
                                precio_minorista=0.0 # Will need calculation
                            )
                            ms.add(new_prod)
                            ms.flush() # get ID
                            pid = new_prod.id
                            # Optionally update the FacturaItem in ProvDB with this new ID
                            # (Skipped for simplicity, but good practice)

                        # Update Stock
                        # Assuming 'Principal' deposit id=1
                        stk = ms.query(StockModel).filter(StockModel.producto_id == pid, StockModel.deposito_id == 1).first()
                        if not stk:
                            stk = StockModel(producto_id=pid, deposito_id=1, cantidad=0)
                            ms.add(stk)

                        # Check bulk/granel logic
                        qty_to_add = it["qty"]
                        prod_obj = ms.query(Producto).get(pid)
                        if prod_obj:
                            # If venta_granel is set, it means the product is sold in smaller units (e.g. Liters)
                            # but bought in packs (e.g. Drums).
                            # We check 'venta_granel' flag.
                            # Also check 'presentacion_cantidad'.
                            is_granel = False
                            try:
                                if hasattr(prod_obj, "venta_granel") and (prod_obj.venta_granel in (1, True, "1")):
                                    is_granel = True
                            except: QMessageBox.information(self, "OK", "Guardado y stock actualizado.")

                            if is_granel:
                                pres = 1.0
                                try:
                                    if hasattr(prod_obj, "presentacion_cantidad"):
                                        pres = float(prod_obj.presentacion_cantidad or 1.0)
                                except: pass
                                if pres > 0:
                                    qty_to_add = it["qty"] * pres

                        stk.cantidad += qty_to_add

                        # Update Cost?
                        prod = ms.query(Producto).get(pid)
                        if prod:
                            prod.costo = it["price"]
                            # Logic to update retail price could go here or trigger a recalc flag

                    ms.commit()

            QMessageBox.information(self, "OK", "Guardado y stock actualizado.")
            self._limpiar_form()
            self.setProperty("current_factura_id", None)
            self.btn_guardar.setText("Guardar Confirmar Stock")

            if callable(self._on_after_save):
                try:
                    self._on_after_save()
                except Exception as e:
                    print(f"on_after_save falló: {e}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")

    def _limpiar_form(self):
        self.txt_numero.clear()
        self.spn_dias.setValue(0)
        self.spn_monto.setValue(0.00)
        self.txt_desc.clear()
        self.spn_pago_efec.setValue(0.00)
        self.spn_pago_transf.setValue(0.00)
        self.spn_pago_cheq.setValue(0.00)
        self.spn_pago_bat.setValue(0.00)
        self.spn_pago_otro.setValue(0.00)
        self.dt_fecha.setDate(QDate.currentDate())
        self.tbl_items.setRowCount(0)
        self.lbl_total_items.setText("Total: $0.00")
        self._recalcular_vto()

    # ---------------- Utils ----------------
    @staticmethod
    def _to_pydate(qdate: QDate) -> date:
        try:
            return date(qdate.year(), qdate.month(), qdate.day())
        except Exception:
            return datetime.now().date()


# ====== Compatibilidad con código existente ======
class FacturasTab(FacturaProveedorWidget):
    """Alias compatible con la importación antigua (main_tab importa FacturasTab)."""
    pass

__all__ = ["FacturaProveedorWidget", "FacturasTab"]
