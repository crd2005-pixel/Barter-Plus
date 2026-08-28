# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QFileDialog, QMessageBox, QDialog, QFormLayout,
    QLineEdit, QComboBox, QCompleter, QDoubleSpinBox, QCheckBox
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
        self.chk_bajo_min.stateChanged.connect(self.load_data)

        self.load_data()

    def showEvent(self, event):
        self.load_data()
        super().showEvent(event)

    # -------------------- Cargar grilla --------------------

    def _apply_filters(self):
        r_sel = getattr(self, 'cb_filtro_rubro', None) and self.cb_filtro_rubro.currentText() or "Todos"
        m_sel = getattr(self, 'cb_filtro_marca', None) and self.cb_filtro_marca.currentText() or "Todos"
        for r in range(self.tbl.rowCount()):
            row_rubro = self.tbl.item(r, 4).text() if self.tbl.item(r, 4) else ""
            row_marca = self.tbl.item(r, 3).text() if self.tbl.item(r, 3) else ""
            hide = False
            if r_sel != "Todos" and row_rubro != r_sel: hide = True
            if not hide and m_sel != "Todos" and row_marca != m_sel: hide = True
            self.tbl.setRowHidden(r, hide)

    def load_data(self):
        if not self.SessionLocal or not self.ProductoModel:
            # QMessageBox.critical(self, "Stock", "No se pudo resolver el modelo de Productos.")
            self.tbl.setRowCount(0)
            return
        try:
            with self.SessionLocal() as s:
                productos_all = s.query(self.ProductoModel).all()
                extras_map = ProductoService.load_all_extras(s, self.ProductoModel)

                def _extra_of(p, key):
                    if hasattr(p, key):
                        return getattr(p, key, None)
                    pid = getattr(p, "id", None)
                    return (extras_map.get(pid) or {}).get(key)

                rows = []
                for p in productos_all:
                    stock_val = ProductoService.get_stock_qty(s, p)
                    stock_min = float(_extra_of(p, "stock_minimo") or 0.0)
                    if self.chk_bajo_min.isChecked():
                        # El filtro sigue siendo "debajo del mínimo" (estricto)
                        if stock_val < stock_min:
                            rows.append((p, stock_val, stock_min))
                    else:
                        rows.append((p, stock_val, stock_min))

                self.tbl.setRowCount(len(rows))
                for i, (p, stock_val, stock_min) in enumerate(rows):
                    cod_barras = str(getattr(p, "codigo_barras", "") or "")
                    id_item = QTableWidgetItem(cod_barras)
                    id_item.setData(Qt.UserRole, getattr(p, "id", None))

                    codigo = str(getattr(p, "codigo", "") or getattr(p, "sku", ""))
                    nombre = str(getattr(p, "descripcion", "") or getattr(p, "nombre", ""))

                    # Marca
                    marca_nombre = ""
                    try:
                        if self.MarcaModel is not None and getattr(p, "marca_id", None):
                            marca = s.query(self.MarcaModel).get(getattr(p, "marca_id"))
                            marca_nombre = getattr(marca, "nombre", "") if marca else ""
                    except Exception:
                        pass

                    rubro = str(getattr(p, "rubro", "") or "")
                    subrubro = str(_extra_of(p, "subrubro") or "")
                    unidad = str(_extra_of(p, "presentacion_unidad") or "")
                    contenido = _extra_of(p, "presentacion_cantidad")
                    try:
                        if contenido is None:
                            contenido = ""
                        else:
                            contenido = float(contenido)
                            contenido = int(contenido) if abs(contenido - int(contenido)) < 1e-9 else round(contenido, 3)
                    except Exception:
                        contenido = ""
                    venta = "Granel" if (_extra_of(p, "venta_granel") in (1, True, "1")) else "Unidad"

                    stock_max = float(_extra_of(p, "stock_maximo") or 0.0)

                    # Datos extra del proveedor
                    prov_data = find_price_plus_iva_for_product(p)
                    prov_code = prov_data.get("codigo", "") if prov_data.get("ok") else ""
                    prov_pres = prov_data.get("presentacion", "")
                    prov_info = prov_data.get("info_extra", "")

                    # Items
                    self.tbl.setItem(i, 0, id_item)
                    self.tbl.setItem(i, 1, QTableWidgetItem(codigo))
                    self.tbl.setItem(i, 2, QTableWidgetItem(nombre))
                    self.tbl.setItem(i, 3, QTableWidgetItem(marca_nombre))

                    self.tbl.setItem(i, 4, QTableWidgetItem(str(prov_code)))
                    self.tbl.setItem(i, 5, QTableWidgetItem(str(prov_pres)))
                    self.tbl.setItem(i, 6, QTableWidgetItem(str(prov_info)))

                    self.tbl.setItem(i, 7, QTableWidgetItem(rubro))
                    self.tbl.setItem(i, 8, QTableWidgetItem(subrubro))
                    self.tbl.setItem(i, 9, QTableWidgetItem(unidad))
                    self.tbl.setItem(i, 10, QTableWidgetItem(str(contenido)))
                    self.tbl.setItem(i, 11, QTableWidgetItem(venta))
                    self.tbl.setItem(i, 12, QTableWidgetItem(str(stock_val)))
                    self.tbl.setItem(i, 13, QTableWidgetItem(str(int(stock_min) if abs(stock_min-int(stock_min))<1e-9 else round(stock_min,3))))
                    self.tbl.setItem(i, 14, QTableWidgetItem(str(int(stock_max) if abs(stock_max-int(stock_max))<1e-9 else round(stock_max,3))))

                    # Resaltado SOLO cuando Stock == Stock Min (tolerancia)
                    if _eq_tol(stock_val, stock_min):
                        brush = QBrush(QColor(90, 0, 0))  # rojo oscuro, tema oscuro
                        for col in range(self.tbl.columnCount()):
                            it = self.tbl.item(i, col)
                            if it:
                                it.setBackground(brush)

                rubros = set()
                marcas = set()
                for r in range(self.tbl.rowCount()):
                    item_r = self.tbl.item(r, 4)
                    item_m = self.tbl.item(r, 3)
                    if item_r and item_r.text(): rubros.add(item_r.text())
                    if item_m and item_m.text(): marcas.add(item_m.text())

                if hasattr(self, 'cb_filtro_rubro'):
                    curr_rubro = self.cb_filtro_rubro.currentText()
                    curr_marca = self.cb_filtro_marca.currentText()
                    self.cb_filtro_rubro.blockSignals(True)
                    self.cb_filtro_marca.blockSignals(True)
                    self.cb_filtro_rubro.clear()
                    self.cb_filtro_rubro.addItem("Todos")
                    self.cb_filtro_rubro.addItems(sorted(list(rubros)))
                    self.cb_filtro_marca.clear()
                    self.cb_filtro_marca.addItem("Todos")
                    self.cb_filtro_marca.addItems(sorted(list(marcas)))
                    idx_r = self.cb_filtro_rubro.findText(curr_rubro)
                    if idx_r >= 0: self.cb_filtro_rubro.setCurrentIndex(idx_r)
                    idx_m = self.cb_filtro_marca.findText(curr_marca)
                    if idx_m >= 0: self.cb_filtro_marca.setCurrentIndex(idx_m)
                    self.cb_filtro_rubro.blockSignals(False)
                    self.cb_filtro_marca.blockSignals(False)
                    self._apply_filters()
                rubros = set()
                marcas = set()
                for r in range(self.tbl.rowCount()):
                    item_r = self.tbl.item(r, 4)
                    item_m = self.tbl.item(r, 3)
                    if item_r and item_r.text(): rubros.add(item_r.text())
                    if item_m and item_m.text(): marcas.add(item_m.text())

                if hasattr(self, 'cb_filtro_rubro'):
                    curr_rubro = self.cb_filtro_rubro.currentText()
                    curr_marca = self.cb_filtro_marca.currentText()
                    self.cb_filtro_rubro.blockSignals(True)
                    self.cb_filtro_marca.blockSignals(True)
                    self.cb_filtro_rubro.clear()
                    self.cb_filtro_rubro.addItem("Todos")
                    self.cb_filtro_rubro.addItems(sorted(list(rubros)))
                    self.cb_filtro_marca.clear()
                    self.cb_filtro_marca.addItem("Todos")
                    self.cb_filtro_marca.addItems(sorted(list(marcas)))
                    idx_r = self.cb_filtro_rubro.findText(curr_rubro)
                    if idx_r >= 0: self.cb_filtro_rubro.setCurrentIndex(idx_r)
                    idx_m = self.cb_filtro_marca.findText(curr_marca)
                    if idx_m >= 0: self.cb_filtro_marca.setCurrentIndex(idx_m)
                    self.cb_filtro_rubro.blockSignals(False)
                    self.cb_filtro_marca.blockSignals(False)
                    self._apply_filters()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el stock:\n{e}")

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
                            marca = s.query(self.MarcaModel).get(getattr(p, "marca_id"))
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
            p = s.query(self.ProductoModel).get(pid)
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
                p = s.query(self.ProductoModel).get(pid)
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
