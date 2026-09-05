import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QLineEdit,
    QLabel, QMessageBox
)
from PyQt5.QtCore import Qt
from sqlalchemy import or_

from db.database import SessionLocal
from db.models.productos import Producto
from db.models.configuracion import Configuracion
from db.models.costos_extra import CostoExtra
from db.models.params import Parametros
import sqlite3

class BaseStockTab(QWidget):
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

        self.init_ui()
        self._cargar_params()
        self._actualizar_combos_filtro()
        self.cargar_datos()

    def init_ui(self):
        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()

        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Buscar (Código o Descripción)...")
        self.txt_buscar.textChanged.connect(self._reset_pagination_and_load)
        top_layout.addWidget(QLabel("Buscar:"))
        top_layout.addWidget(self.txt_buscar)

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

        layout.addLayout(top_layout)

        # Config table specific for Stock
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels([
            "Código", "Marca", "Descripción", "Stock Actual", "Stock Mínimo"
        ])

        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        layout.addWidget(self.tabla)

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
        except Exception:
            pass

    def _reset_pagination_and_load(self):
        self.current_page = 1
        self.cargar_datos()

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.cargar_datos()

    def _next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.cargar_datos()

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

    def cargar_datos(self):
        self.tabla.setRowCount(0)

        try:
            with SessionLocal() as session:
                query = self.get_filtros_query(session)

                self.total_records = query.count()
                self.total_pages = max(1, (self.total_records + self.page_size - 1) // self.page_size)

                self.lbl_page_info.setText(f"Página {self.current_page} de {self.total_pages}")
                self.btn_prev_page.setEnabled(self.current_page > 1)
                self.btn_next_page.setEnabled(self.current_page < self.total_pages)

                offset = (self.current_page - 1) * self.page_size
                productos = query.order_by(Producto.descripcion).offset(offset).limit(self.page_size).all()

                self.tabla.setRowCount(len(productos))

                for row, p in enumerate(productos):
                    # We might need costo logic here depending on how base_stock was used previously
                    # The prompt says rewrite "pestañas precios y stock", which implies both get pagination.

                    self.tabla.setItem(row, 0, QTableWidgetItem(str(p.codigo or "")))
                    self.tabla.setItem(row, 1, QTableWidgetItem(str(p.marca or "")))
                    self.tabla.setItem(row, 2, QTableWidgetItem(str(p.descripcion or "")))

                    stock = getattr(p, "stock", 0.0)
                    stock_min = getattr(p, "stock_minimo", 0.0)

                    item_stock = QTableWidgetItem(str(stock))
                    item_stock.setTextAlignment(Qt.AlignCenter)
                    self.tabla.setItem(row, 3, item_stock)

                    item_min = QTableWidgetItem(str(stock_min))
                    item_min.setTextAlignment(Qt.AlignCenter)
                    self.tabla.setItem(row, 4, item_min)

        except Exception as e:
            pass

    def actualizar(self):
        self._cargar_params()
        self.cargar_datos()
