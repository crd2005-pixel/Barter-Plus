# -*- coding: utf-8 -*-
import os
import math
import datetime as dt
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox
)

from db import SessionLocal, Producto, Stock
from services.solicitud_service import SolicitudService
try:
    from db import Proveedor, Marca
except Exception:
    try:
        from db.models.productos import Marca
    except ImportError:
        Marca = None
    Proveedor = None

# Lista en memoria para mostrar en la tabla (se regenera al cargar)
_GENERATED_LIST = []

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

def _stock_total(session, prod_id):
    # Intentar leer del modelo Producto primero (legacy/simple)
    p = session.query(Producto).get(prod_id)
    if p:
        for campo in ("stock", "existencia", "cantidad", "stock_actual", "cant_actual", "en_stock"):
            if hasattr(p, campo):
                val = getattr(p, campo)
                if val is not None:
                    return float(val)

    # Si no, sumar tabla Stock
    from sqlalchemy import func
    return float(session.query(func.coalesce(func.sum(Stock.cantidad), 0.0))
                 .filter(Stock.producto_id == prod_id).scalar() or 0.0)

def _presentacion_cant(p):
    v = _get(p, "presentacion_cantidad", "presentacion_cant", "unidades_por_caja", "pack_cant",
             "litros_por_envase", "capacidad_litros", default=1)
    q = _as_float(v, 1)
    return q if q > 0 else 1

def _proveedor_de(p, s):
    pid = _get(p, "proveedor_id", "id_proveedor", default=None)
    if Proveedor and pid:
        try:
            pr = s.query(Proveedor).get(pid)
            if pr:
                return getattr(pr, "id", None), getattr(pr, "nombre", "Proveedor")
        except Exception:
            pass
    return None, "Sin proveedor"

def _marca_de(p, s):
    mid = _get(p, "marca_id", default=None)
    if Marca and mid:
        try:
            m = s.query(Marca).get(mid)
            if m:
                return getattr(m, "nombre", "")
        except Exception:
            pass
    return ""

def _build_item_dict(s, p, cantidad_pedido, stock_actual, is_bulto=False):
    prov_id, prov_nom = _proveedor_de(p, s)
    marca = _marca_de(p, s)
    rubro = getattr(p, "rubro", "") or ""

    # El costo almacenado en producto se asume que es "Costo de Compra" (por bulto si se compra por bulto)
    costo = _as_float(_get(p, "costo","costo_unit","ultimo_costo", default=0), 0)

    # Si la cantidad_pedido viene en unidades de stock, pero el costo es por bulto,
    # debemos asegurarnos de que cantidad_pedido sea bultos si is_bulto=True.

    uni = _get(p, "presentacion_unidad","presentacion_tipo","unidad", default="unidad")
    if is_bulto:
        pres = _presentacion_cant(p)
        if pres > 1:
            uni = f"Pack x{int(pres)} {uni}"

    return {
        "ts": dt.datetime.now(),
        "proveedor_id": prov_id,
        "proveedor": prov_nom,
        "rubro": rubro,
        "marca": marca,
        "producto_id": getattr(p, "id", None),
        "producto": getattr(p, "nombre", ""),
        "codigo_barras": getattr(p, "codigo_barras", "") or getattr(p, "sku", "") or "",
        "cantidad": cantidad_pedido,
        "unidad": uni,
        "costo_unit": costo,
        "subtotal": cantidad_pedido * costo,
        "stock_actual": stock_actual,
        "tipo": "AUTO"
    }

def generar_sugerencias_pedido():
    """
    Escanea la base de datos y retorna lista de productos con stock <= mínimo.
    Calcula pedido como (maximo - actual).
    También agrega SOLICITUDES manuales de clientes.
    """
    lista = []
    with SessionLocal() as s:
        # 1. Sugerencias automaticas por stock
        try:
            # Filtrar activos si existe columna
            q = s.query(Producto)
            if hasattr(Producto, "activo"):
                q = q.filter(Producto.activo == True)
            prods = q.all()
        except Exception:
            prods = []

        for p in prods:
            smin = _as_float(_get(p, "stock_minimo","stock_min","minimo", default=0), 0)
            smax = _as_float(_get(p, "stock_maximo","stock_max","maximo", default=0), 0)

            # Si no hay configuración de stock, ignorar (o si min es 0 y max 0)
            if smin <= 0 and smax <= 0:
                continue

            st = _stock_total(s, p.id)

            # Condición: stock estrictamente menor al mínimo (st < smin)
            # El usuario pide: "si es igual o mayor al stock mínimo que no aparezca en la lista"
            if st < smin:
                deficit_stock = 0.0
                if smax > st:
                    deficit_stock = smax - st
                else:
                    # Si max no está configurado o es menor que actual
                    # pedir para llegar a min + un margen (ej una presentación)
                    diff = smin - st
                    if diff < 0: diff = 0
                    pres = _presentacion_cant(p)
                    # Forzamos que se pida algo para superar el minimo
                    base_req = diff + pres if diff == 0 else diff
                    deficit_stock = max(base_req, pres)

                if deficit_stock > 0:
                    # Normalizar a unidades de compra (Bultos) si es granel o presentación > 1
                    pres = _presentacion_cant(p)
                    is_granel = False
                    if hasattr(p, "venta_granel") and (p.venta_granel in (1, True, "1")):
                        is_granel = True

                    qty_final = deficit_stock
                    is_bulto = False

                    if is_granel or pres > 1:
                        # Convertir deficit (unidades stock) a bultos (unidades compra)
                        bultos = deficit_stock / pres
                        # Redondear hacia arriba para comprar bulto cerrado
                        qty_final = math.ceil(bultos)
                        is_bulto = True

                    item = _build_item_dict(s, p, qty_final, st, is_bulto=is_bulto)
                    lista.append(item)

        # 2. Solicitudes manuales (Clientes)
        solicitudes = SolicitudService.listar_pendientes(s)
        for sol in solicitudes:
            lista.append({
                "ts": sol.fecha,
                "proveedor_id": None,
                "proveedor": "SOLICITUD CLIENTE", # Distintivo
                "rubro": "PEDIDO",
                "marca": "",
                "producto_id": None,
                "producto": sol.producto_texto,
                "codigo_barras": "SUGERIDO",
                "cantidad": 1.0, # Default 1
                "unidad": "unidad",
                "costo_unit": 0.0,
                "subtotal": 0.0,
                "stock_actual": 0.0, # No aplica o desconocido
                "tipo": "MANUAL"
            })

    return lista

def _group_by_proveedor(data):
    g = {}
    for it in data:
        g.setdefault(it["proveedor"], []).append(it)
    return g

# -------- UI --------
class PedidosTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Generar Sugerencias (Scan)"); self.btn_refresh.clicked.connect(self._reload_scan)
        self.btn_export = QPushButton("Exportar PDF"); self.btn_export.clicked.connect(self._exportar_pdf)

        bar.addWidget(self.btn_refresh)
        bar.addStretch()
        bar.addWidget(self.btn_export)
        root.addLayout(bar)

        # Tabla
        # Cols: Check, ID, Fecha, Rubro, Marca, Cód., Producto, Stock Act., Cant. Pedir, Costo Total
        headers = ["", "ID", "Fecha", "Rubro", "Marca", "Cód.", "Producto", "Stock Act.", "Cant. Pedir", "Costo Total"]
        self.tbl = QTableWidget(0, len(headers))
        self.tbl.setHorizontalHeaderLabels(headers)
        self.tbl.setColumnWidth(0, 30) # Columna checkbox estrecha
        root.addWidget(self.tbl)

        # Cargar al iniciar
        self._reload_scan()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F5:
            self._reload_scan()
        else:
            super().keyPressEvent(event)

    # Para compatibilidad con main.py
    def refresh(self):
        self._reload_scan()

    def _reload_scan(self):
        global _GENERATED_LIST
        self.tbl.setRowCount(0)
        try:
            _GENERATED_LIST = generar_sugerencias_pedido()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al generar pedidos: {e}")
            _GENERATED_LIST = []

        if not _GENERATED_LIST:
            # self._row_info("— Stock en orden (ninguno bajo mínimo) —")
            pass

        self._fill_table(_GENERATED_LIST)

    def _fill_table(self, items_list):
        if not items_list:
            return

        # Sort by provider then product (agrupación lógica)
        sorted_items = sorted(items_list, key=lambda x: (x.get("proveedor",""), x.get("producto","")))

        self.tbl.setRowCount(len(sorted_items))
        rid = 1
        for r, it in enumerate(sorted_items):
            fecha = it["ts"]
            # prov = it["proveedor"] # Se usa para ordenar pero no se muestra
            rubro = it.get("rubro", "")
            marca = it.get("marca", "")
            prod_nom = it["producto"]
            cod = it.get("codigo_barras", "")
            stock_act = it.get("stock_actual", 0)

            tipo = it.get("tipo", "AUTO")

            stock_str = f"{stock_act:.2f}"
            if tipo == "MANUAL":
                stock_str = "-"

            cant = it["cantidad"]
            c_str = f"{int(cant)}" if abs(cant - int(cant)) < 1e-9 else f"{cant:.2f}"
            uni = it.get("unidad", "") or ""
            cant_full = f"{c_str} {uni}"

            sub = it["subtotal"]

            # Cols:
            # 0: Check, 1: ID, 2: Fecha, 3: Rubro, 4: Marca, 5: Cód., 6: Producto, 7: Stock Act., 8: Cant. Pedir, 9: Costo Total

            item_check = QTableWidgetItem()
            item_check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item_check.setCheckState(Qt.Unchecked)
            self.tbl.setItem(r, 0, item_check)

            item_id = QTableWidgetItem(str(rid)); rid += 1
            self.tbl.setItem(r, 1, item_id)
            self.tbl.setItem(r, 2, QTableWidgetItem(fecha.strftime("%d/%m %H:%M")))

            self.tbl.setItem(r, 3, QTableWidgetItem(rubro))
            self.tbl.setItem(r, 4, QTableWidgetItem(marca))

            self.tbl.setItem(r, 5, QTableWidgetItem(cod))
            self.tbl.setItem(r, 6, QTableWidgetItem(prod_nom))
            self.tbl.setItem(r, 7, QTableWidgetItem(stock_str))
            self.tbl.setItem(r, 8, QTableWidgetItem(cant_full))
            self.tbl.setItem(r, 9, QTableWidgetItem(f"{sub:.2f}"))

            # Resaltar manuales (si aplica)
            if tipo == "MANUAL":
                for c in range(1, 10):
                    it_c = self.tbl.item(r, c)
                    if it_c:
                        it_c.setBackground(Qt.yellow)
                        it_c.setForeground(Qt.black)

    def _row_info(self, text):
        self.tbl.insertRow(0)
        self.tbl.setItem(0, 1, QTableWidgetItem(text))
        for c in range(2, self.tbl.columnCount()):
            self.tbl.setItem(0, c, QTableWidgetItem(""))

    # ------- export -------
    def _exportar_pdf(self):
        if not _GENERATED_LIST:
            QMessageBox.information(self, "Pedidos", "No hay nada para exportar.")
            return

        # 1. Filtrar seleccionados
        # Ojo: la lista _GENERATED_LIST está ordenada distinta en _fill_table.
        # Lo mejor es recorrer la tabla para ver cuáles están chequeados y matchear con la data,
        # O simplemente asumir que el orden visual es el de sorted_items en _fill_table si no cambio nada.
        # Para ser seguro: _fill_table ordena por (proveedor, producto).

        # Reconstruir la lista ordenada igual que la tabla
        sorted_items = sorted(_GENERATED_LIST, key=lambda x: (x.get("proveedor",""), x.get("producto","")))

        items_a_exportar = []
        indices_exportados = []

        for r in range(self.tbl.rowCount()):
            it = self.tbl.item(r, 0)
            if it and it.checkState() == Qt.Checked:
                # Mapear fila r a sorted_items[r]
                if r < len(sorted_items):
                    items_a_exportar.append(sorted_items[r])
                    indices_exportados.append(r)

        if not items_a_exportar:
            QMessageBox.information(self, "Pedidos", "No ha seleccionado ningún item para exportar.")
            return

        ruta = self._make_pdf_path()
        # Pasamos solo los items filtrados a las funciones de exportación
        ok = self._try_export_utils(ruta, items_a_exportar) or \
             self._try_export_reportlab(ruta, items_a_exportar) or \
             self._export_txt_fallback(ruta.replace(".pdf", ".txt"), items_a_exportar)

        if ok:
            # Marcar visualmente como exportados (sin borrar)
            color_exportado = QColor("#c8e6c9") # Verde suave
            for r in indices_exportados:
                # Pintar toda la fila o algunas celdas
                for c in range(1, self.tbl.columnCount()):
                    it = self.tbl.item(r, c)
                    if it:
                        it.setBackground(color_exportado)
                        it.setForeground(Qt.black) # Asegurar legibilidad

            QMessageBox.information(self, "Pedidos", f"Exportado correctamente ({len(items_a_exportar)} items).\n{ruta if ruta else ''}")
        else:
            QMessageBox.critical(self, "Pedidos", "No se pudo exportar.")

    def _make_pdf_path(self):
        try:
            base = os.path.join(os.getcwd(), "pedidos_exportados")
            os.makedirs(base, exist_ok=True)
            fn = f"pedidos_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            return os.path.join(base, fn)
        except Exception:
            return None

    def _try_export_utils(self, ruta_pdf, items_list):
        try:
            from utils.pdf import generar_pedidos_proveedores_pdf
            groups = _group_by_proveedor(items_list)
            generar_pedidos_proveedores_pdf(groups, ruta_pdf)
            return True
        except Exception:
            return False

    def _try_export_reportlab(self, ruta_pdf, items_list):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except Exception:
            return False
        try:
            groups = _group_by_proveedor(items_list)
            c = canvas.Canvas(ruta_pdf, pagesize=A4)
            w, h = A4
            y0 = h - 50
            for prov, items in groups.items():
                y = y0
                c.setFont("Helvetica-Bold", 14); c.drawString(40, y, f"Pedido a proveedor: {prov}"); y -= 18
                c.setFont("Helvetica", 10); c.drawString(40, y, dt.datetime.now().strftime("%Y-%m-%d %H:%M")); y -= 20
                c.setFont("Helvetica-Bold", 10)
                c.drawString(40, y, "Producto"); c.drawString(300, y, "Cant."); c.drawString(360, y, "Costo"); c.drawString(430, y, "Subtotal"); y -= 12
                c.setFont("Helvetica", 10)
                total = 0.0
                for it in items:
                    sub = _as_float(it["subtotal"], 0.0)
                    total += sub
                    c.drawString(40, y, it["producto"][:42])
                    c.drawRightString(340, y, f"{it['cantidad']:.2f} {it.get('unidad','')}")
                    c.drawRightString(420, y, f"{it['costo_unit']:.2f}")
                    c.drawRightString(500, y, f"{sub:.2f}")
                    y -= 12
                    if y < 70:
                        c.showPage(); y = y0
                y -= 8
                c.setFont("Helvetica-Bold", 11)
                c.drawRightString(500, y, f"Total: {total:.2f}")
                c.showPage()
            c.save()
            return True
        except Exception:
            return False

    def _export_txt_fallback(self, ruta_txt, items_list):
        try:
            groups = _group_by_proveedor(items_list)
            os.makedirs(os.path.dirname(ruta_txt), exist_ok=True)
            with open(ruta_txt, "w", encoding="utf-8") as f:
                for prov, items in groups.items():
                    f.write(f"Proveedor: {prov}\nFecha: {dt.datetime.now():%Y-%m-%d %H:%M}\n")
                    total = 0.0
                    for it in items:
                        sub = _as_float(it["subtotal"], 0.0); total += sub
                        f.write(f"  - {it['producto']} (Cod: {it.get('codigo_barras','')}) x {it['cantidad']} {it.get('unidad','')}  "
                                f"@ {it['costo_unit']:.2f}  = {sub:.2f}\n")
                    f.write(f"Total: {total:.2f}\n\n")
            return True
        except Exception:
            return False