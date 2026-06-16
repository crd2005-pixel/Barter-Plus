# proveedores.py
# ===========================
# Pestaña de Proveedores con subpestañas:
#   1. Alta de proveedores
#   2. Listas de precios
#   3. Facturas y pagos
#   4. Comparativa de precios
#   5. Pedidos
# ===========================

import os
import datetime as dt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QGroupBox, QFormLayout, QLineEdit,
    QPushButton, QMessageBox, QComboBox, QHBoxLayout, QLabel, QFileDialog,
    QTableWidget, QTableWidgetItem, QSplitter
)
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtCore import Qt

from db import SessionLocal, Proveedor, ProveedorPrecio, FacturaProveedor, Pasivo, Asiento, CajaMovimiento, BancoMovimiento
from utils import importar_excel_proveedores, importar_pdf_proveedores
from pedidos import PedidosTab   # ✅ import absoluto corregido


# --------------------------
# Subpestaña 1: Alta de proveedores
# --------------------------
class AltaProveedoresTab(QWidget):
    def __init__(self, parent_reload_callback):
        super().__init__()
        self.session = SessionLocal()
        self.parent_reload_callback = parent_reload_callback

        layout = QVBoxLayout(self)

        prov_box = QGroupBox('Alta de proveedor')
        f = QFormLayout(prov_box)
        self.inp_nombre = QLineEdit(); self.inp_cuit = QLineEdit()
        self.inp_tel = QLineEdit(); self.inp_mail = QLineEdit(); self.inp_dir = QLineEdit()
        btn_add = QPushButton("Agregar Proveedor"); btn_add.clicked.connect(self.add_proveedor)
        f.addRow("Nombre:", self.inp_nombre)
        f.addRow("CUIT:", self.inp_cuit)
        f.addRow("Teléfono:", self.inp_tel)
        f.addRow("Email:", self.inp_mail)
        f.addRow("Dirección:", self.inp_dir)
        f.addRow(btn_add)

        layout.addWidget(prov_box)

    def add_proveedor(self):
        s = self.session
        if not self.inp_nombre.text().strip():
            QMessageBox.warning(self,'Falta nombre','Ingrese nombre del proveedor'); return
        p = Proveedor(
            nombre=self.inp_nombre.text().strip(),
            cuit=self.inp_cuit.text().strip(),
            telefono=self.inp_tel.text().strip(),
            email=self.inp_mail.text().strip(),
            direccion=self.inp_dir.text().strip()
        )
        s.add(p); s.commit()
        self.parent_reload_callback()
        QMessageBox.information(self,'OK','Proveedor agregado')
        self.inp_nombre.clear(); self.inp_cuit.clear(); self.inp_tel.clear()
        self.inp_mail.clear(); self.inp_dir.clear()


# --------------------------
# Subpestaña 2: Listas de precios
# --------------------------
class ListasPreciosTab(QWidget):
    def __init__(self, parent_reload_callback):
        super().__init__()
        self.session = SessionLocal()
        self.parent_reload_callback = parent_reload_callback

        splitter = QSplitter(Qt.Vertical)

        # --- Controles superiores ---
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)

        hl = QHBoxLayout()
        self.cbo_prov = QComboBox(); self.reload_provs()
        btn_xls = QPushButton('Importar Excel'); btn_xls.clicked.connect(self.imp_excel)
        btn_pdf = QPushButton('Importar PDF'); btn_pdf.clicked.connect(self.imp_pdf)
        hl.addWidget(QLabel('Proveedor:')); hl.addWidget(self.cbo_prov)
        hl.addWidget(btn_xls); hl.addWidget(btn_pdf)
        top_layout.addLayout(hl)

        fl = QHBoxLayout()
        self.inp_buscar = QLineEdit(); self.inp_buscar.setPlaceholderText("Buscar por código o nombre...")
        btn_buscar = QPushButton("Buscar"); btn_buscar.clicked.connect(self.reload_lista)
        fl.addWidget(QLabel("Filtro:")); fl.addWidget(self.inp_buscar); fl.addWidget(btn_buscar)
        top_layout.addLayout(fl)

        aj_box = QGroupBox("Actualizar precios masivamente")
        aj_lay = QFormLayout(aj_box)
        self.inp_pct = QLineEdit(); self.inp_pct.setValidator(QDoubleValidator(-100.0, 100.0, 2)); self.inp_pct.setText("0")
        self.inp_monto = QLineEdit(); self.inp_monto.setValidator(QDoubleValidator(-1e6, 1e6, 2)); self.inp_monto.setText("0")
        btn_aplicar = QPushButton("Aplicar a lista"); btn_aplicar.clicked.connect(self.aplicar_masivo)
        aj_lay.addRow("Δ % (ej. 10 = +10%, -5 = -5%)", self.inp_pct)
        aj_lay.addRow("Δ Monto fijo (ej. 50 = +50, -20 = -20)", self.inp_monto)
        aj_lay.addRow(btn_aplicar)
        top_layout.addWidget(aj_box)

        btn_reload = QPushButton("Recargar lista")
        btn_reload.clicked.connect(self.reload_lista)
        top_layout.addWidget(btn_reload)

        # --- Tabla inferior ---
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["ID","Código","Nombre","Precio"])
        bottom_layout.addWidget(self.tbl)

        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setSizes([250, 400])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self.reload_lista()

    def reload_provs(self):
        self.cbo_prov.clear()
        for p in self.session.query(Proveedor).order_by(Proveedor.nombre.asc()).all():
            self.cbo_prov.addItem(p.nombre, p.id)

    def imp_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Seleccionar Excel proveedor', os.getcwd(), 'Excel (*.xlsx *.xls)')
        if not path: return
        prov_id = self.cbo_prov.currentData()
        if not prov_id:
            QMessageBox.warning(self, "Proveedor", "Debe seleccionar un proveedor antes de importar.")
            return
        prov = self.session.query(Proveedor).get(prov_id)
        if not prov:
            QMessageBox.warning(self, "Proveedor", "Proveedor no encontrado en la base de datos.")
            return
        importar_excel_proveedores(path, prov.nombre)
        self.reload_lista()

    def imp_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Seleccionar PDF proveedor', os.getcwd(), 'PDF (*.pdf)')
        if not path: return
        prov_id = self.cbo_prov.currentData()
        if not prov_id:
            QMessageBox.warning(self, "Proveedor", "Debe seleccionar un proveedor antes de importar.")
            return
        prov = self.session.query(Proveedor).get(prov_id)
        if not prov:
            QMessageBox.warning(self, "Proveedor", "Proveedor no encontrado en la base de datos.")
            return
        importar_pdf_proveedores(path, prov.nombre)
        self.reload_lista()

    def reload_lista(self):
        self.tbl.setRowCount(0)
        prov_id = self.cbo_prov.currentData()
        if not prov_id: return

        q = self.session.query(ProveedorPrecio).filter(ProveedorPrecio.proveedor_id==prov_id)
        filtro = self.inp_buscar.text().strip()
        if filtro:
            q = q.filter((ProveedorPrecio.codigo.ilike(f"%{filtro}%")) | (ProveedorPrecio.nombre.ilike(f"%{filtro}%")))
        rows = q.order_by(ProveedorPrecio.fecha.desc()).limit(500).all()

        for pp in rows:
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            self.tbl.setItem(r,0,QTableWidgetItem(str(pp.id)))
            self.tbl.setItem(r,1,QTableWidgetItem(pp.codigo or ''))
            self.tbl.setItem(r,2,QTableWidgetItem(pp.nombre or ''))
            self.tbl.setItem(r,3,QTableWidgetItem(f"{pp.precio:.2f}"))

    def aplicar_masivo(self):
        prov_id = self.cbo_prov.currentData()
        if not prov_id:
            QMessageBox.warning(self, "Proveedor", "Seleccione un proveedor."); return
        try:
            pct = float(self.inp_pct.text() or 0)
            monto = float(self.inp_monto.text() or 0)
        except:
            QMessageBox.warning(self, "Valores inválidos", "Ingrese números correctos."); return

        q = self.session.query(ProveedorPrecio).filter(ProveedorPrecio.proveedor_id==prov_id)
        rows = q.all()
        for pp in rows:
            base = float(pp.precio or 0)
            nuevo = base * (1 + pct/100.0) + monto
            pp.precio = max(0, nuevo)
        self.session.commit()
        QMessageBox.information(self, "OK", f"Actualizados {len(rows)} precios.")
        self.reload_lista()


# --------------------------
# Subpestaña 3: Facturas y pagos
# --------------------------
class FacturasTab(QWidget):
    def __init__(self, parent_reload_callback):
        super().__init__()
        self.session = SessionLocal()
        self.parent_reload_callback = parent_reload_callback

        layout = QVBoxLayout(self)

        self.tbl = QTableWidget(0,7)
        self.tbl.setHorizontalHeaderLabels(["ID","Proveedor","Fecha","Vencimiento","Rubro","Total","Estado"])
        layout.addWidget(self.tbl)

        btn_reload = QPushButton("Recargar facturas")
        btn_reload.clicked.connect(self.reload_facturas)
        layout.addWidget(btn_reload)

        self.reload_facturas()

    def reload_facturas(self):
        s = self.session
        rows = s.query(FacturaProveedor).order_by(FacturaProveedor.fecha.desc()).all()
        self.tbl.setRowCount(0)
        for f in rows:
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            self.tbl.setItem(r,0,QTableWidgetItem(str(f.id)))
            self.tbl.setItem(r,1,QTableWidgetItem(f.proveedor.nombre if f.proveedor else ''))
            self.tbl.setItem(r,2,QTableWidgetItem(f.fecha.strftime("%d/%m/%Y")))
            self.tbl.setItem(r,3,QTableWidgetItem(f.vencimiento.strftime("%d/%m/%Y")))
            self.tbl.setItem(r,4,QTableWidgetItem(f.rubro or ''))
            self.tbl.setItem(r,5,QTableWidgetItem(f"{f.total:.2f}"))
            self.tbl.setItem(r,6,QTableWidgetItem(f.estado))


# --------------------------
# Subpestaña 4: Comparativa de precios
# --------------------------
class ComparativaPreciosTab(QWidget):
    def __init__(self):
        super().__init__()
        self.session = SessionLocal()

        splitter = QSplitter(Qt.Vertical)

        # --- Controles superiores ---
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        self.inp_buscar = QLineEdit(); self.inp_buscar.setPlaceholderText("Buscar producto...")
        btn_buscar = QPushButton("Buscar"); btn_buscar.clicked.connect(self.reload)
        top_layout.addWidget(self.inp_buscar); top_layout.addWidget(btn_buscar)

        # --- Tabla comparativa ---
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        self.tbl = QTableWidget(0, 0)
        bottom_layout.addWidget(self.tbl)

        btn_reload = QPushButton("Recargar comparativa"); btn_reload.clicked.connect(self.reload)
        bottom_layout.addWidget(btn_reload)

        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setSizes([80, 500])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self.reload()

    def reload(self):
        self.tbl.setRowCount(0)
        proveedores = self.session.query(Proveedor).order_by(Proveedor.nombre.asc()).all()
        prov_names = [p.nombre for p in proveedores]
        headers = ["Código", "Producto"] + prov_names
        self.tbl.setColumnCount(len(headers))
        self.tbl.setHorizontalHeaderLabels(headers)

        filtro = self.inp_buscar.text().strip()
        q = self.session.query(ProveedorPrecio).order_by(ProveedorPrecio.nombre.asc(), ProveedorPrecio.fecha.desc())
        if filtro:
            q = q.filter((ProveedorPrecio.codigo.ilike(f"%{filtro}%")) | (ProveedorPrecio.nombre.ilike(f"%{filtro}%")))
        precios = q.all()

        agrupados = {}
        for pp in precios:
            key = pp.codigo or pp.nombre
            if key not in agrupados:
                agrupados[key] = {"codigo": pp.codigo, "nombre": pp.nombre, "precios": {}}
            agrupados[key]["precios"][pp.proveedor.nombre] = pp.precio

        for prod in agrupados.values():
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(prod["codigo"] or ""))
            self.tbl.setItem(r, 1, QTableWidgetItem(prod["nombre"] or ""))

            precios_fila = []
            for i, prov in enumerate(prov_names, start=2):
                precio = prod["precios"].get(prov, None)
                if precio:
                    item = QTableWidgetItem(f"{precio:.2f}")
                    self.tbl.setItem(r, i, item)
                    precios_fila.append((i, precio))

            if precios_fila:
                min_col, min_val = min(precios_fila, key=lambda x: x[1])
                self.tbl.item(r, min_col).setBackground(Qt.green)


# --------------------------
# Tab principal de Proveedores
# --------------------------
class ProveedoresTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.alta_tab = AltaProveedoresTab(self.reload_provs_global)
        self.listas_tab = ListasPreciosTab(self.reload_provs_global)
        self.facturas_tab = FacturasTab(self.reload_provs_global)
        self.comparativa_tab = ComparativaPreciosTab()
        self.pedidos_tab = PedidosTab()   # ✅ nueva subpestaña

        self.tabs.addTab(self.alta_tab, "General")
        self.tabs.addTab(self.listas_tab, "Listas de Precios")
        self.tabs.addTab(self.facturas_tab, "Facturas y Pagos")
        self.tabs.addTab(self.comparativa_tab, "Comparativa de Precios")
        self.tabs.addTab(self.pedidos_tab, "Pedidos")   # ✅ aparece en la interfaz

        layout.addWidget(self.tabs)

    def reload_provs_global(self):
        self.listas_tab.reload_provs()
        self.facturas_tab.reload_facturas()
