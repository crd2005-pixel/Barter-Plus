import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QLineEdit,
    QLabel, QMessageBox, QProgressDialog, QApplication
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from sqlalchemy import or_

from db.database import SessionLocal
from db.models.productos import Producto
from db.models.configuracion import Configuracion
from db.models.costos_extra import CostoExtra
from db.models.params import Parametros
from servicios.listas_cache import listas_cache

class PreciosTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.margen_global = 0.0
        self.dolar = 1.0
        self.descuento_general = 0.0

        # Pagination state
        self.page_size = 50
        self.current_page = 1
        self.total_pages = 1
        self.total_records = 0

        self._init_ui()
        self._cargar_params()
        self._actualizar_combos_filtro()
        self._cargar_datos()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Controles superiores
        top_layout = QHBoxLayout()

        # Búsqueda general
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Buscar (Código o Descripción)...")
        self.txt_buscar.textChanged.connect(self._reset_pagination_and_load)
        top_layout.addWidget(QLabel("Buscar:"))
        top_layout.addWidget(self.txt_buscar)

        # Combos
        self.combo_marca = QComboBox()
        self.combo_marca.currentTextChanged.connect(self._reset_pagination_and_load)

        self.combo_rubro = QComboBox()
        self.combo_rubro.currentTextChanged.connect(self._reset_pagination_and_load)

        self.combo_subrubro = QComboBox()
        self.combo_subrubro.currentTextChanged.connect(self._reset_pagination_and_load)

        top_layout.addWidget(QLabel("Marca:"))
        top_layout.addWidget(self.combo_marca)
        top_layout.addWidget(QLabel("Rubro:"))
        top_layout.addWidget(self.combo_rubro)
        top_layout.addWidget(QLabel("Subrubro:"))
        top_layout.addWidget(self.combo_subrubro)

        # Botón Imprimir Precios
        self.btn_imprimir = QPushButton("Imprimir Lista")
        self.btn_imprimir.clicked.connect(self.main_window.imprimir_lista_precios)
        top_layout.addWidget(self.btn_imprimir)

        layout.addLayout(top_layout)

        # Tabla
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(8)
        self.tabla.setHorizontalHeaderLabels([
            "Código", "Marca", "Descripción", "Costo Lista", "Prorrateo",
            "Costo Real", "Margen %", "Precio Final"
        ])

        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)

        layout.addWidget(self.tabla)

        # Paginación UI
        pagination_layout = QHBoxLayout()

        self.btn_prev_page = QPushButton("<< Anterior")
        self.btn_prev_page.clicked.connect(self._prev_page)
        self.btn_prev_page.setEnabled(False)

        self.lbl_page_info = QLabel("Página 1 de 1")
        self.lbl_page_info.setAlignment(Qt.AlignCenter)

        self.btn_next_page = QPushButton("Siguiente >>")
        self.btn_next_page.clicked.connect(self._next_page)
        self.btn_next_page.setEnabled(False)

        pagination_layout.addWidget(self.btn_prev_page)
        pagination_layout.addWidget(self.lbl_page_info)
        pagination_layout.addWidget(self.btn_next_page)

        layout.addLayout(pagination_layout)

        self.setLayout(layout)

    def _actualizar_combos_filtro(self):
        try:
            with SessionLocal() as session:
                marcas = session.query(Producto.marca).filter(Producto.marca != None).distinct().order_by(Producto.marca).all()
                rubros = session.query(Producto.rubro).filter(Producto.rubro != None).distinct().order_by(Producto.rubro).all()
                subrubros = session.query(Producto.subrubro).filter(Producto.subrubro != None).distinct().order_by(Producto.subrubro).all()

                self.combo_marca.clear()
                self.combo_marca.addItem("Todas")
                for m in marcas:
                    if m[0]: self.combo_marca.addItem(m[0])

                self.combo_rubro.clear()
                self.combo_rubro.addItem("Todos")
                for r in rubros:
                    if r[0]: self.combo_rubro.addItem(r[0])

                self.combo_subrubro.clear()
                self.combo_subrubro.addItem("Todos")
                for sr in subrubros:
                    if sr[0]: self.combo_subrubro.addItem(sr[0])
        except Exception as e:
            pass

    def _reset_pagination_and_load(self):
        self.current_page = 1
        self._cargar_datos()

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._cargar_datos()

    def _next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._cargar_datos()

    def _cargar_params(self):
        try:
            with SessionLocal() as session:
                conf = session.query(Configuracion).first()
                if conf:
                    self.margen_global = float(conf.margen_general or 0.0)
                    self.descuento_general = float(conf.descuento_general or 0.0)

                param_dolar = session.query(Parametros).filter_by(clave="dolar").first()
                if param_dolar:
                    self.dolar = float(param_dolar.valor)
                else:
                    self.dolar = 1.0
        except:
            self.margen_global = 0.0
            self.dolar = 1.0
            self.descuento_general = 0.0

    def get_filtros_query(self, session):
        query = session.query(Producto)

        texto = self.txt_buscar.text().strip().lower()
        if texto:
            search = f"%{texto}%"
            query = query.filter(or_(
                Producto.codigo.ilike(search),
                Producto.descripcion.ilike(search)
            ))

        marca = self.combo_marca.currentText()
        if marca and marca != "Todas":
            query = query.filter(Producto.marca == marca)

        rubro = self.combo_rubro.currentText()
        if rubro and rubro != "Todos":
            query = query.filter(Producto.rubro == rubro)

        subrubro = self.combo_subrubro.currentText()
        if subrubro and subrubro != "Todos":
            query = query.filter(Producto.subrubro == subrubro)

        return query

    def _cargar_datos(self):
        self.tabla.setRowCount(0)

        try:
            with SessionLocal() as session:
                query = self.get_filtros_query(session)

                # Cuenta total para paginación
                self.total_records = query.count()
                self.total_pages = max(1, (self.total_records + self.page_size - 1) // self.page_size)

                # Actualiza UI de paginación
                self.lbl_page_info.setText(f"Página {self.current_page} de {self.total_pages}")
                self.btn_prev_page.setEnabled(self.current_page > 1)
                self.btn_next_page.setEnabled(self.current_page < self.total_pages)

                # Pagina los resultados
                offset = (self.current_page - 1) * self.page_size
                productos = query.order_by(Producto.descripcion).offset(offset).limit(self.page_size).all()

                self.tabla.setRowCount(len(productos))

                # Import para leer costo directo
                import sqlite3

                for row, p in enumerate(productos):
                    # 1. Obtener costo maestro
                    costo_base_maestro = getattr(p, "costo", 0.0) or 0.0
                    try:
                        conn = sqlite3.connect("proveedores/data/proveedores.sqlite3")
                        c = conn.cursor()
                        c.execute("SELECT costo_neto FROM productos_maestro WHERE sku_interno = ? LIMIT 1", (p.codigo,))
                        res = c.fetchone()
                        if res and res[0]:
                            costo_base_maestro = float(res[0])
                        conn.close()
                    except:
                        pass

                    # 2. Otros datos
                    margen_manual = getattr(p, 'margen', 0.0) or 0.0
                    margen_subrubro = getattr(p, 'margen_subrubro', 0.0) or 0.0
                    margen_rubro = getattr(p, 'margen_rubro', 0.0) or 0.0

                    costos_extras = session.query(CostoExtra).filter_by(codigo_producto=p.codigo).all()

                    # 3. Calcular
                    es_dolar = (getattr(p, 'moneda', 'ARS') == 'USD')
                    tasa = self.dolar if es_dolar else 1.0

                    costo_lista = costo_base_maestro * tasa

                    suma_porcentaje = sum(float(c.valor) for c in costos_extras if c.tipo == 'porcentaje')
                    suma_fijo = sum(float(c.valor) for c in costos_extras if c.tipo == 'fijo')
                    prorrateo = (costo_lista * (suma_porcentaje/100)) + suma_fijo

                    costo_real = costo_lista + prorrateo

                    if margen_manual > 0:
                        margen_final = margen_manual
                    elif margen_subrubro > 0:
                        margen_final = margen_subrubro
                    elif margen_rubro > 0:
                        margen_final = margen_rubro
                    else:
                        margen_final = self.margen_global

                    precio_final = costo_real * (1 + (margen_final/100))

                    if self.descuento_general > 0:
                        precio_final = precio_final * (1 - (self.descuento_general/100))

                    # 4. Insertar en tabla
                    self.tabla.setItem(row, 0, QTableWidgetItem(str(p.codigo or "")))
                    self.tabla.setItem(row, 1, QTableWidgetItem(str(p.marca or "")))
                    self.tabla.setItem(row, 2, QTableWidgetItem(str(p.descripcion or "")))

                    item_lista = QTableWidgetItem(f"${costo_lista:,.2f}")
                    item_lista.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.tabla.setItem(row, 3, item_lista)

                    item_pro = QTableWidgetItem(f"${prorrateo:,.2f}")
                    item_pro.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.tabla.setItem(row, 4, item_pro)

                    item_real = QTableWidgetItem(f"${costo_real:,.2f}")
                    item_real.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.tabla.setItem(row, 5, item_real)

                    item_margen = QTableWidgetItem(f"{margen_final:,.2f}%")
                    item_margen.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.tabla.setItem(row, 6, item_margen)

                    item_final = QTableWidgetItem(f"${precio_final:,.2f}")
                    item_final.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                    f = QFont()
                    f.setBold(True)
                    item_final.setFont(f)

                    if p.id_promocion:
                        item_final.setForeground(QColor("red"))
                    else:
                        item_final.setForeground(QColor("blue"))

                    self.tabla.setItem(row, 7, item_final)

        except Exception as e:
            pass

    def actualizar(self):
        self._cargar_params()
        self._cargar_datos()
