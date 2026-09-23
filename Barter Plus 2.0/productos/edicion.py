from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QPushButton,
    QHBoxLayout, QLabel, QMessageBox, QCompleter, QGroupBox, QVBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from db import SessionLocal, Producto
try:
    from db.models.proveedores import Proveedor
except ImportError:
    Proveedor = None
try:
    from db.models.productos import Marca
except ImportError:
    Marca = None

from proveedores.bootstrap import bootstrap as prov_bootstrap

try:
    _prov_ns = prov_bootstrap()
    ProvSession = _prov_ns.get("SessionLocal")
    ItemListaProveedor = _prov_ns.get("ItemListaProveedor")
except Exception:
    ProvSession = None
    ItemListaProveedor = None

from .utils import precio_final_sugerido, mapa_stock_valor, get_param_float
from .listas_bridge import find_price_plus_iva_for_product

_RUBROS = ["Baterias", "Lubricantes", "Filtros", "Otro"]

class _BuscarEnListaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Buscar en Lista de Proveedores")
        self.resize(700, 400)
        self.selected_item = None

        lay = QVBoxLayout(self)

        h = QHBoxLayout()
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("Buscar por descripción, código o marca...")
        self.inp_search.returnPressed.connect(self._buscar)
        btn_search = QPushButton("Buscar")
        btn_search.clicked.connect(self._buscar)
        h.addWidget(self.inp_search)
        h.addWidget(btn_search)
        lay.addLayout(h)

        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Código", "Descripción", "Marca", "Costo", "Proveedor"])
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.cellDoubleClicked.connect(self._seleccionar)
        lay.addWidget(self.tbl)

        btn_sel = QPushButton("Seleccionar")
        btn_sel.clicked.connect(self._seleccionar)
        lay.addWidget(btn_sel)

    def _buscar(self):
        txt = self.inp_search.text().strip()
        if not txt or not ProvSession or not ItemListaProveedor:
            return

        self.tbl.setRowCount(0)
        with ProvSession() as s:
            # Búsqueda simple con like
            q = s.query(ItemListaProveedor).filter(
                (ItemListaProveedor.descripcion.ilike(f"%{txt}%")) |
                (ItemListaProveedor.producto_codigo.ilike(f"%{txt}%")) |
                (ItemListaProveedor.marca.ilike(f"%{txt}%"))
            ).limit(50)

            for item in q.all():
                r = self.tbl.rowCount()
                self.tbl.insertRow(r)
                self.tbl.setItem(r, 0, QTableWidgetItem(item.producto_codigo or ""))
                self.tbl.setItem(r, 1, QTableWidgetItem(item.descripcion or ""))
                self.tbl.setItem(r, 2, QTableWidgetItem(item.marca or ""))
                self.tbl.setItem(r, 3, QTableWidgetItem(f"{item.precio:.2f}"))
                self.tbl.setItem(r, 4, QTableWidgetItem(str(item.lista_id)))

                # Guardar objeto completo en data
                self.tbl.item(r, 0).setData(Qt.UserRole, {
                    "codigo": item.producto_codigo,
                    "descripcion": item.descripcion,
                    "marca": item.marca,
                    "precio": item.precio,
                    "lista_id": item.lista_id
                })

    def _seleccionar(self):
        r = self.tbl.currentRow()
        if r >= 0:
            self.selected_item = self.tbl.item(r, 0).data(Qt.UserRole)
            self.accept()

class ProductoEditorDialog(QDialog):
    def __init__(self, producto_id=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Producto")
        self.setMinimumWidth(600)
        self.producto_id = producto_id
        self._auto_match_data = None
        self._loaded_prov_id = None # Para detectar cambios manuales

        # Timer para debounce (Inicializar ANTES de conectar señales que lo usan)
        self._timer_check = QTimer()
        self._timer_check.setSingleShot(True)
        self._timer_check.timeout.connect(self._perform_auto_check)

        layout = QVBoxLayout(self)

        # --- Cabecera: Buscador ---
        gb_link = QGroupBox("Vinculación con Proveedor")
        hl = QHBoxLayout(gb_link)
        btn_link = QPushButton("Buscar Manualmente...")
        btn_link.clicked.connect(self._abrir_buscador_listas)
        hl.addWidget(btn_link)
        self.lbl_linked = QLabel("Escaneando...")
        self.lbl_linked.setStyleSheet("color: blue; font-weight: bold;")
        hl.addWidget(self.lbl_linked)
        layout.addWidget(gb_link)

        # --- Formulario ---
        f = QFormLayout()

        self.inp_cod_barras = QLineEdit()
        self.inp_cod_barras.setPlaceholderText("Escaneá o generá (ID principal)")
        self.inp_cod_barras.textChanged.connect(self._schedule_auto_check)

        self.inp_sku = QLineEdit()
        self.inp_sku.setPlaceholderText("Código interno / de fábrica")
        self.inp_sku.textChanged.connect(self._schedule_auto_check)

        self.inp_cod_prov = QLineEdit()
        self.inp_cod_prov.setPlaceholderText("Código exacto en lista proveedor")
        self.inp_cod_prov.textChanged.connect(self._schedule_auto_check)

        self.inp_equivalencia = QLineEdit()
        self.inp_equivalencia.setPlaceholderText("Código compartido (agrupa stock para pedidos)")
        self.inp_equivalencia.textChanged.connect(self._schedule_auto_check)

        self.inp_nombre = QLineEdit()
        self.inp_nombre.setPlaceholderText("Descripción del producto")
        self.inp_nombre.textChanged.connect(self._schedule_auto_check)

        self.cmb_marca = QComboBox()
        self.cmb_marca.setEditable(True)
        self.cmb_marca.setPlaceholderText("Escriba o seleccione...")

        self.cmb_rubro = QComboBox()
        self.cmb_rubro.setEditable(True)
        self.cmb_rubro.addItems(_RUBROS)

        self.cmb_subrubro = QComboBox()
        self.cmb_subrubro.setEditable(True)

        self.cmb_prov = QComboBox() # Proveedor
        self.cmb_prov.currentIndexChanged.connect(self._schedule_auto_check)
        self._cargar_proveedores()
        self._cargar_marcas()
        self._cargar_rubros_subrubros()

        f.addRow("Código Barras (ID):", self.inp_cod_barras)
        f.addRow("Código Interno (SKU):", self.inp_sku)
        f.addRow("Código Proveedor:", self.inp_cod_prov)
        f.addRow("Cod. Equivalencia:", self.inp_equivalencia)
        f.addRow("Descripción / Nombre:", self.inp_nombre)
        f.addRow("Marca:", self.cmb_marca)
        f.addRow("Rubro:", self.cmb_rubro)
        f.addRow("Subrubro:", self.cmb_subrubro)
        f.addRow("Proveedor:", self.cmb_prov)

        # --- Datos adicionales del Proveedor (Solo lectura, para referencia) ---
        self.lbl_prov_pres = QLabel("-")
        self.lbl_prov_extra = QLabel("-")
        self.lbl_prov_pres.setStyleSheet("color: #555;")
        self.lbl_prov_extra.setStyleSheet("color: #555;")

        f.addRow("Presentación (Lista):", self.lbl_prov_pres)
        f.addRow("Info Extra (Lista):", self.lbl_prov_extra)

        layout.addLayout(f)

        # --- Precios Automáticos ---
        gb_precio = QGroupBox("Precios (Automáticos)")
        fp = QFormLayout(gb_precio)

        self.lbl_costo_base = QLabel("$0.00")
        self.lbl_costo_iva = QLabel("$0.00 (Base + IVA Lista)")

        self.sp_pmin = QDoubleSpinBox(); self.sp_pmin.setRange(0, 1e9); self.sp_pmin.setPrefix("$ ")
        self.sp_pmay = QDoubleSpinBox(); self.sp_pmay.setRange(0, 1e9); self.sp_pmay.setPrefix("$ ")

        # Hidden storage for values
        self._val_costo = 0.0
        self._val_iva = 21.0

        fp.addRow("Costo Base (Lista):", self.lbl_costo_base)
        fp.addRow("Costo + IVA:", self.lbl_costo_iva)
        fp.addRow("Precio Minorista:", self.sp_pmin)
        fp.addRow("Precio Mayorista:", self.sp_pmay)

        layout.addWidget(gb_precio)

        # --- Stock ---
        gb_stock = QGroupBox("Stock y Presentación")
        fs = QFormLayout(gb_stock)

        self.sp_smin = QDoubleSpinBox(); self.sp_smin.setRange(0, 1e5)
        self.sp_smax = QDoubleSpinBox(); self.sp_smax.setRange(0, 1e5)

        self.chk_granel = QCheckBox("Venta fraccionada / granel")
        self.inp_pres_unidad = QLineEdit("Unidad")
        self.sp_pres_cant = QDoubleSpinBox(); self.sp_pres_cant.setRange(0.001, 10000); self.sp_pres_cant.setValue(1.0)

        r_st = QHBoxLayout()
        r_st.addWidget(QLabel("Min:")); r_st.addWidget(self.sp_smin)
        r_st.addWidget(QLabel("Max:")); r_st.addWidget(self.sp_smax)
        fs.addRow("Límites Stock:", r_st)

        fs.addRow("", self.chk_granel)

        r_pr = QHBoxLayout()
        r_pr.addWidget(QLabel("Unidad:")); r_pr.addWidget(self.inp_pres_unidad)
        r_pr.addWidget(QLabel("Cant/Pack:")); r_pr.addWidget(self.sp_pres_cant)
        fs.addRow("Presentación:", r_pr)

        layout.addWidget(gb_stock)

        # Botones finales
        h = QHBoxLayout()
        btn_ok = QPushButton("Guardar"); btn_ok.clicked.connect(self._guardar)
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        h.addStretch()
        h.addWidget(btn_ok)
        h.addWidget(btn_cancel)
        layout.addLayout(h)

        if self.producto_id:
            self._load()
        else:
            self._perform_auto_check(update_prices=True)

    def _schedule_auto_check(self):
        self._timer_check.start(600) # 600ms delay

    def _perform_auto_check(self, update_prices=True):
        # Crear objeto dummy con los datos actuales
        class DummyProd:
            def __init__(self):
                self.id = None
                self.codigo = ""
                self.sku = ""
                self.codigo_proveedor = ""
                self.cod = ""
                self.nombre = ""
                self.proveedor_id = None
                self.rubro = ""
                self.costo = 0.0
                self.iva = 21.0
                self.stock = 0.0
                self.cantidad = 0.0

        current_pid = self.cmb_prov.currentData()

        p = DummyProd()
        p.codigo_proveedor = self.inp_cod_prov.text().strip()
        p.codigo = p.codigo_proveedor or self.inp_sku.text().strip() or self.inp_cod_barras.text().strip()
        p.nombre = self.inp_nombre.text().strip()
        p.proveedor_id = current_pid
        p.rubro = self.cmb_rubro.currentText()

        res = find_price_plus_iva_for_product(p)

        # Permitir fallback global SOLO si:
        # 1. No se ha seleccionado proveedor (es nuevo o 'Sin proveedor')
        # 2. O el proveedor seleccionado es el que estaba guardado (estamos validando el link existente)
        # Esto evita que si el usuario cambia el proveedor manualmente a uno nuevo, el sistema lo revierta automáticamente.
        allow_fallback = (not current_pid) or (hasattr(self, "_loaded_prov_id") and current_pid == self._loaded_prov_id)

        if not res["ok"] and p.proveedor_id and allow_fallback:
            # Quitamos prov_id para buscar en todas las listas
            bkp_pid = p.proveedor_id
            p.proveedor_id = None
            res_global = find_price_plus_iva_for_product(p)
            p.proveedor_id = bkp_pid # restaurar

            if res_global["ok"]:
                res = res_global

        self._auto_match_data = res

        if res["ok"]:
            # Auto-detectar proveedor
            found_pid = res.get("proveedor_id")

            # Actualizar combo solo si es necesario y seguro (ver lógica fallback arriba)
            if found_pid and (not current_pid or (allow_fallback and current_pid != found_pid)):
                idx = -1
                for i in range(self.cmb_prov.count()):
                    if self.cmb_prov.itemData(i) == found_pid:
                        idx = i; break
                if idx >= 0:
                     self.cmb_prov.setCurrentIndex(idx)

            # --- AUTO-LINK: Si no hay código proveedor, llenar con el código encontrado (que puede ser la descripción) ---
            # Esto fija el vínculo para el futuro.
            if not self.inp_cod_prov.text().strip():
                found_code = res.get("codigo")
                if found_code:
                    self.inp_cod_prov.blockSignals(True)
                    self.inp_cod_prov.setText(found_code)
                    self.inp_cod_prov.blockSignals(False)

            self.lbl_linked.setText(f"Encontrado: {res['descripcion_lista']} ({res['marca']}) - Lista #{res['lista_id']}")
            self.lbl_linked.setStyleSheet("color: green; font-weight: bold;")

            self.lbl_prov_pres.setText(res.get("presentacion", "") or "-")
            self.lbl_prov_extra.setText(res.get("info_extra", "") or "-")

            self._val_costo = res["base"]
            self._val_iva = 21.0
            costo_final = res["mas_iva"]

            self.lbl_costo_base.setText(f"${res['base']:.2f}")
            self.lbl_costo_iva.setText(f"${costo_final:.2f}")

            # Recalcular sugeridos
            total_variables = get_param_float("var_cost_total_mensual", 0.0)
            base_map = mapa_stock_valor()

            p.costo = res["base"]
            p.iva = 21.0
            pm, py = precio_final_sugerido(p, total_variables, base_map)

            if update_prices:
                self.sp_pmin.setValue(pm)
                self.sp_pmay.setValue(py)

        else:
            self.lbl_linked.setText("No encontrado en listas (se usará costo manual 0)")
            self.lbl_linked.setStyleSheet("color: red;")
            self.lbl_prov_pres.setText("-")
            self.lbl_prov_extra.setText("-")

            self.lbl_costo_base.setText("$0.00")
            self.lbl_costo_iva.setText("$0.00")
            self._val_costo = 0.0

            if update_prices:
                self.sp_pmin.setValue(0.0)
                self.sp_pmay.setValue(0.0)

    def _abrir_buscador_listas(self):
        if ProvSession is None:
            QMessageBox.warning(self, "Listas", "No hay conexión con la base de proveedores.")
            return
        dlg = _BuscarEnListaDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.selected_item:
            it = dlg.selected_item

            # Usar código del ítem. Si no tiene, usar descripción.
            code_to_use = it["codigo"]
            if not code_to_use:
                code_to_use = it["descripcion"]
            self.inp_cod_prov.setText(code_to_use or "")

            if not self.inp_nombre.text().strip():
                self.inp_nombre.setText(it["descripcion"] or "")

            self.cmb_marca.setEditText(it["marca"] or "")

            self._perform_auto_check()

    def _cargar_proveedores(self):
        self.cmb_prov.addItem("— Sin proveedor —", None)
        if Proveedor:
            try:
                with SessionLocal() as s:
                    for p in s.query(Proveedor).order_by(Proveedor.nombre).all():
                        self.cmb_prov.addItem(p.nombre, p.id)
            except: pass

    def _cargar_marcas(self):
        if Marca:
            try:
                with SessionLocal() as s:
                    for m in s.query(Marca).order_by(Marca.nombre).all():
                        self.cmb_marca.addItem(m.nombre)
            except: pass

    def _cargar_rubros_subrubros(self):
        try:
            with SessionLocal() as s:
                # Load existing Rubros from DB distinct values
                existing_rubros = [r[0] for r in s.query(Producto.rubro).distinct().filter(Producto.rubro != None).order_by(Producto.rubro).all()]

                # Merge with defaults, keeping uniqueness and sorting
                rubros_set = set(_RUBROS)
                for r in existing_rubros:
                    if r: rubros_set.add(r)

                # Clear and re-add
                self.cmb_rubro.clear()
                self.cmb_rubro.addItems(sorted(list(rubros_set)))

                # Load existing Subrubros
                existing_subrubros = [r[0] for r in s.query(Producto.subrubro).distinct().filter(Producto.subrubro != None).order_by(Producto.subrubro).all()]
                self.cmb_subrubro.clear()
                if existing_subrubros:
                    self.cmb_subrubro.addItems([s for s in existing_subrubros if s])

        except Exception:
            pass

    def _load(self):
        with SessionLocal() as s:
            p = s.get(Producto, self.producto_id)
            if not p: return

            self.inp_cod_barras.setText(p.codigo_barras or "")
            self.inp_sku.setText(p.sku or "")
            self.inp_equivalencia.setText(getattr(p, "codigo_equivalencia", "") or "")
            self.inp_nombre.setText(p.nombre or "")
            self.cmb_rubro.setEditText(p.rubro or "")
            self.cmb_subrubro.setEditText(p.subrubro or "")
            self.inp_cod_prov.setText(getattr(p, "codigo_proveedor", "") or "")

            # Marca
            m_nom = ""
            if p.marca_id and Marca:
                m = s.get(Marca, p.marca_id)
                if m: m_nom = m.nombre
            self.cmb_marca.setEditText(m_nom)

            # Proveedor
            idx = 0
            prov_id = getattr(p, "proveedor_id", None)
            if prov_id:
                for i in range(self.cmb_prov.count()):
                    if self.cmb_prov.itemData(i) == prov_id:
                        idx = i; break
            self.cmb_prov.setCurrentIndex(idx)
            self._loaded_prov_id = prov_id # Guardar para detectar cambios manuales

            self.sp_smin.setValue(float(getattr(p, "stock_minimo", 0)))
            self.sp_smax.setValue(float(getattr(p, "stock_maximo", 0)))

            es_granel = False
            if hasattr(p, "venta_granel") and p.venta_granel:
                es_granel = True
            self.chk_granel.setChecked(es_granel)

            self.inp_pres_unidad.setText(getattr(p, "presentacion_unidad", "Unidad") or "Unidad")
            self.sp_pres_cant.setValue(float(getattr(p, "presentacion_cantidad", 1.0) or 1.0))

            self.sp_pmin.setValue(float(getattr(p, "precio_minorista", 0.0) or 0.0))
            self.sp_pmay.setValue(float(getattr(p, "precio_mayorista", 0.0) or 0.0))

            # Initial check (no actualizar precios, respetar los cargados)
            self._perform_auto_check(update_prices=False)

    def _guardar(self):
        nombre = self.inp_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Error", "La descripción/nombre es obligatoria.")
            return

        with SessionLocal() as s:
            if self.producto_id:
                p = s.get(Producto, self.producto_id)
            else:
                p = Producto()
                s.add(p)

            p.codigo_barras = self.inp_cod_barras.text().strip() or None
            p.sku = self.inp_sku.text().strip() or None
            p.codigo_proveedor = self.inp_cod_prov.text().strip() or None
            p.codigo_equivalencia = self.inp_equivalencia.text().strip() or None
            p.nombre = nombre
            p.rubro = self.cmb_rubro.currentText().strip() or None
            p.subrubro = self.cmb_subrubro.currentText().strip() or None
            p.proveedor_id = self.cmb_prov.currentData()

            m_txt = self.cmb_marca.currentText().strip()
            if m_txt and Marca:
                m = s.query(Marca).filter(Marca.nombre == m_txt).first()
                if not m:
                    m = Marca(nombre=m_txt)
                    s.add(m); s.flush()
                p.marca_id = m.id

            # Save automatically calculated prices
            p.costo = self._val_costo
            p.iva = self._val_iva
            p.precio_minorista = self.sp_pmin.value()
            p.precio_mayorista = self.sp_pmay.value()

            p.stock_minimo = self.sp_smin.value()
            p.stock_maximo = self.sp_smax.value()

            p.venta_granel = 1 if self.chk_granel.isChecked() else 0
            p.presentacion_unidad = self.inp_pres_unidad.text().strip()
            p.presentacion_cantidad = self.sp_pres_cant.value()

            s.commit()

        self.accept()
