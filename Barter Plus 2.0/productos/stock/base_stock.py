# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QFileDialog, QMessageBox, QDialog, QFormLayout,
    QLineEdit, QComboBox, QCompleter, QDoubleSpinBox, QCheckBox, QLabel
)
from PyQt5.QtCore import Qt
    # QColor/QBrush para resaltado
from PyQt5.QtGui import QColor, QBrush
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime

from productos.edicion import ProductoEditorDialog  # Usa el editor centralizado si es posible
from productos.listas_bridge import find_price_plus_iva_for_product # Para traer datos extras del proveedor
from .import_excel import ImportExcelDialog
from services.producto_service import ProductoService

try:
    from db.models.productos import Stock as StockModel
except ImportError:
    try:
        from db import Stock as StockModel
    except ImportError:
        StockModel = None

# -------------------- Comparación con tolerancia --------------------
def _eq_tol(a, b, tol=1e-6):
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return a == b


# ======================================================================
# UI Stock
# ======================================================================
class StockRubroGroup(QWidget):
    """
    Stock general (sin IVA/costos). ID visible = código de barras.
    Columnas:
      Cód. barras | Código | Nombre | Marca | Rubro | Subrubro | Unidad | Contenido | Venta | Stock | Stock Min | Stock Max
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.SessionLocal, self.ProductoModel, self.RubroModel, self.MarcaModel = ProductoService.resolve_backend()

        if self.SessionLocal and self.ProductoModel:
            with self.SessionLocal() as s:
                ProductoService.ensure_extra_columns(s, self.ProductoModel)

        lay = QVBoxLayout(self)
        header = QHBoxLayout()

        self.btn_agregar = QPushButton("Agregar producto")
        self.btn_ajustar = QPushButton("Ajustar stock")
        self.btn_importar = QPushButton("Importar Excel")
        self.btn_exportar = QPushButton("Exportar PDF")
        self.btn_editar = QPushButton("Modificar producto")
        self.btn_borrar = QPushButton("Borrar producto")
        self.chk_bajo_min = QCheckBox("Solo bajo mínimo")

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


        header.addWidget(self.btn_agregar)
        header.addWidget(self.btn_ajustar)
        header.addWidget(self.btn_importar)
        header.addWidget(self.btn_exportar)
        header.addWidget(self.btn_editar)
        header.addWidget(self.btn_borrar)
        header.addWidget(self.chk_bajo_min)
        lay.addLayout(header)

        self.tbl = QTableWidget()
        self.tbl.setColumnCount(15)
        self.tbl.setHorizontalHeaderLabels([
            "Cód. barras","Código","Nombre","Marca",
            "Cód. Prov", "Presentación", "Info Extra",
            "Rubro","Subrubro",
            "Unidad","Contenido","Venta","Stock","Stock Min","Stock Max"
        ])
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        lay.addWidget(self.tbl)

        self.btn_agregar.clicked.connect(self._nuevo_producto)
        self.btn_ajustar.clicked.connect(self._abrir_ajuste_stock)
        self.btn_importar.clicked.connect(self._importar_excel)
        self.btn_exportar.clicked.connect(self._exportar_pdf)
        self.btn_editar.clicked.connect(self._editar_producto)
        self.btn_borrar.clicked.connect(self._borrar_producto)
        self.chk_bajo_min.stateChanged.connect(self._reset_page_and_load)

        # Controles de Paginacion
        self.lay_paginacion = QHBoxLayout()
        self.btn_prev = QPushButton("< Anterior")
        self.lbl_page = QLabel("Página 1")
        self.btn_next = QPushButton("Siguiente >")

        self.btn_prev.clicked.connect(self._page_prev)
        self.btn_next.clicked.connect(self._page_next)

        self.lay_paginacion.addStretch()
        self.lay_paginacion.addWidget(self.btn_prev)
        self.lay_paginacion.addWidget(self.lbl_page)
        self.lay_paginacion.addWidget(self.btn_next)
        self.lay_paginacion.addStretch()

        self.current_page = 0
        self.page_size = 50
        self.total_pages = 1
        self._filtered_indices = []

        lay.addLayout(self.lay_paginacion)
        self.load_data()

    def showEvent(self, event):
        self.load_data()
        super().showEvent(event)

    # -------------------- Cargar grilla --------------------

    def _reset_page_and_load(self):
        self.current_page = 0
        self.load_data()

    def _page_prev(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.load_data()

    def _page_next(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.load_data()

    def _populate_combos(self):
        if not self.SessionLocal or not self.ProductoModel: return
        try:
            with self.SessionLocal() as s:
                marcas = [r[0] for r in s.query(self.ProductoModel.marca).distinct().all() if r[0]]
                rubros = [r[0] for r in s.query(self.ProductoModel.rubro).distinct().all() if r[0]]
                subrubros = [r[0] for r in s.query(self.ProductoModel.subrubro).distinct().all() if r[0]]

                self.cmb_marca.blockSignals(True)
                self.cmb_rubro.blockSignals(True)
                self.cmb_subrubro.blockSignals(True)

                self.cmb_marca.clear()
                self.cmb_marca.addItem("Todas")
                self.cmb_marca.addItems(sorted(marcas))

                self.cmb_rubro.clear()
                self.cmb_rubro.addItem("Todos")
                self.cmb_rubro.addItems(sorted(rubros))

                self.cmb_subrubro.clear()
                self.cmb_subrubro.addItem("Todos")
                self.cmb_subrubro.addItems(sorted(subrubros))

                self.cmb_marca.blockSignals(False)
                self.cmb_rubro.blockSignals(False)
                self.cmb_subrubro.blockSignals(False)
        except Exception:
            pass

    def _aplicar_filtros(self):
        self._reset_page_and_load()

    def load_data(self):
        if not self.SessionLocal or not self.ProductoModel:
            self.tbl.setRowCount(0)
            return

        self.tbl.setUpdatesEnabled(False)
        self.tbl.setSortingEnabled(False)
        self.tbl.setRowCount(0)

        try:
            with self.SessionLocal() as s:
                q = s.query(self.ProductoModel)

                f_marca = self.cmb_marca.currentText()
                if f_marca and f_marca != "Todas":
                    q = q.filter(self.ProductoModel.marca == f_marca)

                f_rubro = self.cmb_rubro.currentText()
                if f_rubro and f_rubro != "Todos":
                    q = q.filter(self.ProductoModel.rubro == f_rubro)

                f_subrubro = self.cmb_subrubro.currentText()
                if f_subrubro and f_subrubro != "Todos":
                    q = q.filter(self.ProductoModel.subrubro == f_subrubro)

                f_reciente = self.chk_recientes.isChecked()
                if f_reciente:
                    import datetime
                    hoy = datetime.datetime.now().date()
                    from sqlalchemy import cast, Date
                    q = q.filter(cast(self.ProductoModel.creado_en, Date) == hoy)

                all_prods = q.order_by(self.ProductoModel.nombre.asc()).all()
                extras_map = ProductoService.load_all_extras(s, self.ProductoModel)

                def _extra_of(p, key):
                    if hasattr(p, key):
                        return getattr(p, key, None)
                    return (extras_map.get(p.id) or {}).get(key)

                filtered_prods = []
                for p in all_prods:
                    stock_val = ProductoService.get_stock_qty(s, p)
                    stock_min = float(_extra_of(p, "stock_minimo") or 0.0)

                    if self.chk_bajo_min.isChecked() and stock_val >= stock_min:
                        continue
                    filtered_prods.append((p, stock_val, stock_min))

                total_items = len(filtered_prods)
                self.total_pages = max(1, (total_items + self.page_size - 1) // self.page_size)

                if self.current_page >= self.total_pages:
                    self.current_page = max(0, self.total_pages - 1)

                self.lbl_page.setText(f"Página {self.current_page + 1} de {self.total_pages}")

                start_idx = self.current_page * self.page_size
                end_idx = min(start_idx + self.page_size, total_items)
                page_data = filtered_prods[start_idx:end_idx]

                from PyQt5.QtWidgets import QTableWidgetItem
                from PyQt5.QtCore import Qt

                for page_row, (p, stock_val, stock_min) in enumerate(page_data):
                    self.tbl.insertRow(page_row)

                    marca_nombre = ""
                    if hasattr(p, "marca_rel") and p.marca_rel:
                        marca_nombre = p.marca_rel.nombre

                    pres = getattr(p, "presentacion", "") or ""
                    if hasattr(p, "presentacion_rel") and p.presentacion_rel:
                        pres = p.presentacion_rel.nombre

                    stock_max = float(_extra_of(p, "stock_maximo") or 0.0)

                    cb = ""
                    for f_cb in ("codigo_barras", "barcode", "cb", "ean"):
                        v = getattr(p, f_cb, None)
                        if v:
                            cb = str(v)
                            break

                    cod = ""
                    for f_c in ("codigo", "codigo_interno", "cod", "sku"):
                        v = getattr(p, f_c, None)
                        if v:
                            cod = str(v)
                            break

                    d = {
                        "id": p.id,
                        "codigo_barras": cb,
                        "codigo": cod,
                        "nombre": getattr(p, "nombre", "") or "",
                        "marca": getattr(p, "marca", "") or marca_nombre,
                        "codigo_proveedor": getattr(p, "codigo_proveedor", "") or "",
                        "pres": pres,
                        "info_extra": getattr(p, "info_extra", "") or "",
                        "rubro": getattr(p, "rubro", "") or "",
                        "subrubro": getattr(p, "subrubro", "") or "",
                        "presentacion_unidad": getattr(p, "presentacion_unidad", "") or "",
                        "presentacion_cantidad": float(getattr(p, "presentacion_cantidad", 1.0) or 1.0),
                        "venta_granel": bool(getattr(p, "venta_granel", 0) in (1, True, "1")),
                        "stock_val": stock_val,
                        "stock_min": stock_min,
                        "stock_max": stock_max
                    }

                    it_cb_item = QTableWidgetItem(d["codigo_barras"])
                    it_cb_item.setData(Qt.UserRole, d["id"])
                    self.tbl.setItem(page_row, 0, it_cb_item)
                    self.tbl.setItem(page_row, 1, QTableWidgetItem(d["codigo"]))
                    self.tbl.setItem(page_row, 2, QTableWidgetItem(d["nombre"]))
                    self.tbl.setItem(page_row, 3, QTableWidgetItem(d["marca"]))
                    self.tbl.setItem(page_row, 4, QTableWidgetItem(d["codigo_proveedor"]))
                    self.tbl.setItem(page_row, 5, QTableWidgetItem(d["pres"]))
                    self.tbl.setItem(page_row, 6, QTableWidgetItem(d["info_extra"]))
                    self.tbl.setItem(page_row, 7, QTableWidgetItem(d["rubro"]))
                    self.tbl.setItem(page_row, 8, QTableWidgetItem(d["subrubro"]))
                    self.tbl.setItem(page_row, 9, QTableWidgetItem(d["presentacion_unidad"]))
                    self.tbl.setItem(page_row, 10, QTableWidgetItem(f'{d["presentacion_cantidad"]:g}'))

                    granel_txt = "Granel" if d["venta_granel"] else "Unidad"
                    self.tbl.setItem(page_row, 11, QTableWidgetItem(granel_txt))

                    it_s = QTableWidgetItem(f'{d["stock_val"]:g}')
                    it_s.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.tbl.setItem(page_row, 12, it_s)

                    it_min = QTableWidgetItem(f'{d["stock_min"]:g}')
                    it_min.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.tbl.setItem(page_row, 13, it_min)

                    it_max = QTableWidgetItem(f'{d["stock_max"]:g}')
                    it_max.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.tbl.setItem(page_row, 14, it_max)

                    if d["stock_val"] < d["stock_min"]:
                        for c in range(15):
                            it = self.tbl.item(page_row, c)
                            if it:
                                it.setForeground(Qt.red)

        except Exception as e:
            pass

        self.tbl.resizeColumnsToContents()
        self.tbl.setUpdatesEnabled(True)
        self.tbl.setSortingEnabled(True)

    def _current_product_id(self):
        row = self.tbl.currentRow()
        if row < 0:
            return None
        item = self.tbl.item(row, 0)
        if not item:
            return None
        return item.data(Qt.UserRole)

    # -------------------- Exportar PDF --------------------
    def _exportar_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", "inventario_stock.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            c = canvas.Canvas(path, pagesize=A4)
            w, h = A4
            margin = 40
            y = h - margin
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin, y, "Inventario de stock")
            c.setFont("Helvetica", 9)
            y -= 14
            c.drawString(margin, y, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            y -= 20

            headers = ["Cód. barras","Código","Nombre","Marca","Rubro","Subrubro","Unidad","Contenido","Venta","Stock","Stock Min","Stock Max"]
            colw = [90, 70, 120, 80, 80, 80, 55, 55, 55, 50, 60, 60]
            c.setFont("Helvetica-Bold", 9)
            x = margin
            for i, htxt in enumerate(headers):
                c.drawString(x, y, htxt)
                x += colw[i]
            y -= 12
            c.setFont("Helvetica", 8)

            with self.SessionLocal() as s:
                productos = s.query(self.ProductoModel).all()
                extras_map = ProductoService.load_all_extras(s, self.ProductoModel)
                for p in productos:
                    if y < margin + 40:
                        c.showPage()
                        y = h - margin
                        c.setFont("Helvetica-Bold", 12)
                        c.drawString(margin, y, "Inventario de stock")
                        c.setFont("Helvetica", 9)
                        y -= 14
                        c.drawString(margin, y, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                        y -= 20
                        c.setFont("Helvetica-Bold", 9)
                        x = margin
                        for i, htxt in enumerate(headers):
                            c.drawString(x, y, htxt)
                            x += colw[i]
                        y -= 12
                        c.setFont("Helvetica", 8)

                    pid = getattr(p, "id", None)
                    em = extras_map.get(pid, {})

                    cod_barras = str(getattr(p, "codigo_barras", "") or "")
                    codigo = str(getattr(p, "codigo", "") or getattr(p, "sku", ""))
                    nombre = str(getattr(p, "descripcion", "") or getattr(p, "nombre", ""))
                    marca_nombre = ""
                    try:
                        if self.MarcaModel is not None and getattr(p, "marca_id", None):
                            marca = s.get(self.MarcaModel, getattr(p, "marca_id"))
                            marca_nombre = getattr(marca, "nombre", "") if marca else ""
                    except Exception:
                        pass
                    rubro = str(getattr(p, "rubro", "") or "")

                    subrubro = getattr(p, "subrubro", None) if hasattr(p, "subrubro") else em.get("subrubro")
                    unidad = getattr(p, "presentacion_unidad", None) if hasattr(p, "presentacion_unidad") else em.get("presentacion_unidad")
                    contenido = getattr(p, "presentacion_cantidad", None) if hasattr(p, "presentacion_cantidad") else em.get("presentacion_cantidad")
                    venta_granel = getattr(p, "venta_granel", None) if hasattr(p, "venta_granel") else em.get("venta_granel")
                    stock_min = getattr(p, "stock_minimo", None) if hasattr(p, "stock_minimo") else em.get("stock_minimo")
                    stock_max = getattr(p, "stock_maximo", None) if hasattr(p, "stock_maximo") else em.get("stock_maximo")

                    try:
                        contenido = "" if contenido is None else (int(contenido) if abs(float(contenido)-int(contenido))<1e-9 else round(float(contenido),3))
                    except Exception:
                        contenido = ""
                    venta = "Granel" if (venta_granel in (1, True, "1")) else "Unidad"

                    stock_val = ProductoService.get_stock_qty(s, p)
                    stock_min = float(stock_min or 0.0)
                    stock_max = float(stock_max or 0.0)

                    row = [
                        cod_barras, codigo, nombre, marca_nombre, rubro,
                        str(subrubro or ""), str(unidad or ""), str(contenido), venta, str(stock_val),
                        str(int(stock_min) if abs(stock_min-int(stock_min))<1e-9 else round(stock_min,3)),
                        str(int(stock_max) if abs(stock_max-int(stock_max))<1e-9 else round(stock_max,3))
                    ]
                    x = margin
                    for i2, txt in enumerate(row):
                        c.drawString(x, y, str(txt)[:32])
                        x += colw[i2]
                    y -= 12
            c.save()
            QMessageBox.information(self, "PDF", "Inventario exportado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "PDF", f"No se pudo exportar:\n{e}")

    # -------------------- CRUD --------------------
    def _editar_producto(self):
        pid = self._current_product_id()
        if pid is None:
            QMessageBox.warning(self, "Modificar producto", "Seleccioná un producto de la tabla.")
            return

        # USA EL EDITOR CENTRALIZADO QUE TIENE PROVEEDOR Y STOCK
        try:
            dlg = ProductoEditorDialog(producto_id=pid, parent=self)
        except Exception as e:
            QMessageBox.critical(self, "Modificar producto", f"No se pudo abrir el editor.\n{e}")
            return

        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def _borrar_producto(self):
        pid = self._current_product_id()
        if pid is None:
            QMessageBox.warning(self, "Borrar producto", "Seleccioná un producto.")
            return
        if not self.SessionLocal or not self.ProductoModel:
            QMessageBox.critical(self, "Borrar producto", "Backend no disponible.")
            return
        resp = QMessageBox.question(
            self, "Borrar producto",
            "¿Eliminar el producto seleccionado y su stock asociado?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return
        with self.SessionLocal() as s:
            p = s.get(self.ProductoModel, pid)
            if not p:
                QMessageBox.warning(self, "Borrar", "El producto ya no existe.")
            else:
                if StockModel is not None:
                    try:
                        s.query(StockModel).filter(StockModel.producto_id == pid).delete()
                    except Exception:
                        pass
                s.delete(p)
                s.commit()
        self.load_data()

    def _nuevo_producto(self):
        # USA EL EDITOR CENTRALIZADO PARA NUEVO TAMBIEN
        try:
            dlg = ProductoEditorDialog(producto_id=None, parent=self)
        except Exception as e:
            QMessageBox.critical(self, "Nuevo producto", f"No se pudo abrir el editor.\n{e}")
            return

        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def _abrir_ajuste_stock(self):
        if not self.SessionLocal or not self.ProductoModel:
            QMessageBox.critical(self, "Ajuste", "Backend no disponible.")
            return
        row = self.tbl.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ajuste", "Seleccione un producto.")
            return
        pid = self._current_product_id()
        if pid is None:
            QMessageBox.warning(self, "Ajuste", "No se pudo resolver el ID del producto.")
            return
        dlg = _AjusteStockDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        datos = dlg.datos()
        cant = datos["cantidad"]
        try:
            with self.SessionLocal() as s:
                p = s.get(self.ProductoModel, pid)
                if not p:
                    QMessageBox.warning(self, "Ajuste", "El producto ya no existe.")
                    return
                ProductoService.ajustar_stock(s, p, cant)
                s.add(p); s.commit()
        except Exception as e:
            QMessageBox.critical(self, "Ajuste", f"No se pudo ajustar:\n{e}")
            return
        self.load_data()

    def _importar_excel(self):
        if not self.SessionLocal or not self.ProductoModel:
            QMessageBox.critical(self, "Error", "No se puede importar: Base de datos no disponible.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo Excel", "", "Excel (*.xlsx *.xlsm *.xltx *.xltm)"
        )
        if not file_path:
            return

        dlg = ImportExcelDialog(self, session_factory=self.SessionLocal, producto_model=self.ProductoModel)
        dlg.load_file(file_path)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()


# ===================== Diálogos auxiliares (Ajuste stock) =====================
class _AjusteStockDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustar stock")
        lay = QFormLayout(self)
        self.spn_cant = QDoubleSpinBox(self); self.spn_cant.setRange(-1_000_000.0, 1_000_000.0); self.spn_cant.setDecimals(3)
        self.txt_obs = QLineEdit(self); self.txt_obs.setPlaceholderText("Motivo del ajuste (informativo)")
        lay.addRow("Cantidad (+/-):", self.spn_cant)
        lay.addRow("Observación:", self.txt_obs)
        hb = QHBoxLayout(); ok = QPushButton("Aplicar"); cancel = QPushButton("Cancelar")
        hb.addWidget(ok); hb.addWidget(cancel); lay.addRow(hb)
        ok.clicked.connect(self.accept); cancel.clicked.connect(self.reject)
    def datos(self):
        return {"cantidad": float(self.spn_cant.value()), "obs": (self.txt_obs.text() or "").strip()}
