from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QLabel, QFormLayout, QMessageBox, QDoubleSpinBox, QComboBox, QSplitter, QDialogButtonBox
)
from PyQt6.QtCore import Qt
from services.producto_service import ProductoService
from ui.components.pagination import PaginationWidget

class ProductoDialog(QDialog):
    def __init__(self, parent=None, producto=None):
        super().__init__(parent)
        self.producto = producto
        self.producto_id = producto.id if producto else None

        self.setWindowTitle("Nuevo Producto" if not producto else "Editar Producto")
        self.resize(500, 450)

        self.layout = QFormLayout(self)

        self.sku_input = QLineEdit()
        self.nombre_input = QLineEdit()
        self.codigo_input = QLineEdit()

        self.combo_proveedor = QComboBox()
        self.combo_rubro = QComboBox()
        self.combo_marca = QComboBox()

        self.costo_input = QDoubleSpinBox()
        self.costo_input.setMaximum(9999999.99)
        self.costo_input.setDecimals(2)

        self.margen_input = QDoubleSpinBox()
        self.margen_input.setMaximum(99.99) # Margen no puede ser >= 100
        self.margen_input.setDecimals(2)
        self.margen_input.setValue(30.0) # Margen default 30%

        self.stock_input = QDoubleSpinBox()
        self.stock_input.setMaximum(999999.0)
        self.stock_input.setDecimals(2)
        self.stock_input.setValue(0.0)

        self.stock_min_input = QDoubleSpinBox()
        self.stock_min_input.setMaximum(999999.0)
        self.stock_min_input.setDecimals(2)
        self.stock_min_input.setValue(0.0)

        self.stock_max_input = QDoubleSpinBox()
        self.stock_max_input.setMaximum(999999.0)
        self.stock_max_input.setDecimals(2)
        self.stock_max_input.setValue(0.0)

        from PyQt6.QtWidgets import QCheckBox
        self.es_granel_check = QCheckBox("Se vende a granel")
        self.divisor_granel_input = QDoubleSpinBox()
        self.divisor_granel_input.setRange(1.0, 999999.0)
        self.divisor_granel_input.setValue(1.0)
        self.divisor_granel_input.setEnabled(False)

        self.precio_final_label = QLabel("$ 0.00")
        self.precio_final_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.layout.addRow("SKU Interno:", self.sku_input)
        self.layout.addRow("Nombre:", self.nombre_input)
        self.layout.addRow("Código de Barras (EAN):", self.codigo_input)

        self.layout.addRow("Proveedor:", self.combo_proveedor)
        self.layout.addRow("Categoría/Rubro:", self.combo_rubro)
        self.layout.addRow("Marca:", self.combo_marca)

        # Grupo de Stock
        stock_layout = QHBoxLayout()
        stock_layout.addWidget(QLabel("Act:"))
        stock_layout.addWidget(self.stock_input)
        stock_layout.addWidget(QLabel("Mín:"))
        stock_layout.addWidget(self.stock_min_input)
        stock_layout.addWidget(QLabel("Máx:"))
        stock_layout.addWidget(self.stock_max_input)
        self.layout.addRow("Inventario:", stock_layout)

        # Grupo de Granel
        granel_layout = QHBoxLayout()
        granel_layout.addWidget(self.es_granel_check)
        granel_layout.addWidget(QLabel("Partes/Divisor:"))
        granel_layout.addWidget(self.divisor_granel_input)
        self.layout.addRow("Fraccionamiento:", granel_layout)

        self.layout.addRow("Costo Base (Unidad entera):", self.costo_input)
        self.layout.addRow("Margen (%):", self.margen_input)
        self.layout.addRow("Precio Final Calculado:", self.precio_final_label)

        # Conectar señales para cálculo en tiempo real
        self.costo_input.valueChanged.connect(self.recalcular_precio)
        self.margen_input.valueChanged.connect(self.recalcular_precio)
        self.es_granel_check.stateChanged.connect(self.toggle_granel)

        # Botones
        self.btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.btn_box.accepted.connect(self.guardar)
        self.btn_box.rejected.connect(self.reject)
        self.layout.addRow(self.btn_box)

        self.cargar_relaciones()
        self.cargar_datos()

    def toggle_granel(self):
        self.divisor_granel_input.setEnabled(self.es_granel_check.isChecked())

    def cargar_relaciones(self):
        provs, cats, marcas = ProductoService.obtener_diccionarios_relaciones()

        self.combo_proveedor.addItem("-- Ninguno --", None)
        for p in provs: self.combo_proveedor.addItem(p['nombre'], p['id'])

        self.combo_rubro.addItem("-- Ninguna --", None)
        for c in cats: self.combo_rubro.addItem(c['nombre'], c['id'])

        self.combo_marca.addItem("-- Ninguna --", None)
        for m in marcas: self.combo_marca.addItem(m['nombre'], m['id'])

    def recalcular_precio(self):
        costo = self.costo_input.value()
        margen = self.margen_input.value()
        try:
            pf = ProductoService.calcular_precio_final(costo, margen)
            self.precio_final_label.setText(f"$ {pf:.2f}")
        except ValueError:
            self.precio_final_label.setText("Error (Margen >= 100%)")

    def cargar_datos(self):
        if self.producto:
            self.sku_input.setText(self.producto.sku or "")
            self.sku_input.setEnabled(False) # No editable si ya existe

            self.nombre_input.setText(self.producto.nombre)
            self.codigo_input.setText(self.producto.codigo_barras or "")

            # Combos
            if self.producto.proveedor_id:
                index = self.combo_proveedor.findData(self.producto.proveedor_id)
                if index >= 0: self.combo_proveedor.setCurrentIndex(index)
            if self.producto.categoria_id:
                index = self.combo_rubro.findData(self.producto.categoria_id)
                if index >= 0: self.combo_rubro.setCurrentIndex(index)
            if self.producto.marca_id:
                index = self.combo_marca.findData(self.producto.marca_id)
                if index >= 0: self.combo_marca.setCurrentIndex(index)

            self.stock_input.setValue(self.producto.stock_actual)
            self.stock_min_input.setValue(self.producto.stock_minimo)
            self.stock_max_input.setValue(self.producto.stock_maximo)

            self.es_granel_check.setChecked(self.producto.es_granel)
            self.divisor_granel_input.setValue(self.producto.divisor_granel if self.producto.divisor_granel else 1.0)

            self.costo_input.setValue(self.producto.costo)
            m_inv = ProductoService.calcular_margen_inverso(self.producto.costo, self.producto.precio_minorista)
            self.margen_input.setValue(m_inv)
            self.recalcular_precio()

    def guardar(self):
        sku = self.sku_input.text().strip()
        nombre = self.nombre_input.text().strip()
        codigo = self.codigo_input.text().strip()
        prov_id = self.combo_proveedor.currentData()
        rubro_id = self.combo_rubro.currentData()
        marca_id = self.combo_marca.currentData()
        costo = self.costo_input.value()
        margen = self.margen_input.value()
        stock = self.stock_input.value()
        stock_min = self.stock_min_input.value()
        stock_max = self.stock_max_input.value()
        es_granel = self.es_granel_check.isChecked()
        divisor = self.divisor_granel_input.value() if es_granel else 1.0

        if not nombre:
            QMessageBox.warning(self, "Error", "El nombre es obligatorio.")
            return

        try:
            if not self.producto_id:
                nuevo = ProductoService.crear_producto(
                    sku=sku if sku else None,
                    nombre=nombre,
                    costo=costo,
                    codigo_barras=codigo if codigo else None,
                    stock_inicial=stock,
                    es_granel=es_granel,
                    divisor_granel=divisor,
                    stock_minimo=stock_min,
                    stock_maximo=stock_max,
                    proveedor_id=prov_id,
                    categoria_id=rubro_id,
                    marca_id=marca_id
                )
                ProductoService.actualizar_precio(nuevo.id, margen)
            else:
                ProductoService.actualizar_producto_manual(
                    producto_id=self.producto_id,
                    nombre=nombre,
                    codigo_barras=codigo,
                    costo=costo,
                    margen=margen,
                    stock=stock,
                    es_granel=es_granel,
                    divisor_granel=divisor,
                    stock_minimo=stock_min,
                    stock_maximo=stock_max,
                    proveedor_id=prov_id,
                    categoria_id=rubro_id,
                    marca_id=marca_id
                )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))


class ProductosTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.productos_db = []

        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # Contenedor superior (Formularios/Filtros)
        self.top_widget = QWidget()
        from PyQt6.QtWidgets import QSizePolicy
        self.top_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.top_layout = QVBoxLayout(self.top_widget)
        self.top_layout.setContentsMargins(0, 0, 0, 0)

        # --- Barra superior (Buscador y Acciones) ---
        self.top_bar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por nombre, código...")
        self.search_input.setMinimumWidth(300)
        self.search_input.textChanged.connect(self.cargar_datos)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self.cargar_datos)

        self.btn_nuevo = QPushButton("Nuevo Producto Manual")
        self.btn_editar = QPushButton("Editar / Stock")
        self.btn_eliminar = QPushButton("Eliminar (Deshabilitado)")
        self.btn_eliminar.setEnabled(False) # Por seguridad

        self.btn_nuevo.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold;")
        self.btn_editar.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")

        self.top_bar.addWidget(self.search_input)
        self.top_bar.addWidget(self.btn_buscar)
        self.top_bar.addStretch()
        self.top_bar.addWidget(self.btn_nuevo)
        self.top_bar.addWidget(self.btn_editar)
        self.top_bar.addWidget(self.btn_eliminar)

        self.top_layout.addLayout(self.top_bar)

        # Contenedor inferior (Grilla)
        self.bottom_widget = QWidget()
        self.bottom_layout = QVBoxLayout(self.bottom_widget)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)

        # --- Tabla de Productos ---
        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels(["ID", "SKU", "Cód. Barras", "Nombre", "Stock", "Costo", "Precio Final"])

        # Ergonomía Global: Columnas redimensionables interactivamente
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla.horizontalHeader().setStretchLastSection(True)

        # Anchos sugeridos iniciales
        self.tabla.setColumnWidth(0, 50)
        self.tabla.setColumnWidth(1, 100)
        self.tabla.setColumnWidth(2, 120)
        self.tabla.setColumnWidth(3, 300)
        self.tabla.setColumnWidth(4, 80)

        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)

        self.bottom_layout.addWidget(self.tabla)

        self.paginacion = PaginationWidget(limit=50)
        self.paginacion.page_changed.connect(self.render_tabla_pagina)
        self.bottom_layout.addWidget(self.paginacion)

        self.splitter.addWidget(self.top_widget)
        self.splitter.addWidget(self.bottom_widget)
        # Establecer tamaño relativo (20% top, 80% grid)
        self.splitter.setSizes([100, 400])

        self.layout.addWidget(self.splitter)

        # --- Conexiones ---
        self.btn_nuevo.clicked.connect(self.abrir_dialogo_nuevo)
        self.btn_editar.clicked.connect(self.abrir_dialogo_editar)

        # Cargar datos iniciales
        self.cargar_datos()

    def cargar_datos(self):
        busqueda = self.search_input.text().strip()
        self.productos_db = ProductoService.listar_todos(busqueda)
        self.paginacion.set_total_items(len(self.productos_db))

    def showEvent(self, event):
        """
        Sincronización de Estado:
        Refresca automáticamente la grilla al cambiar a esta pestaña.
        Garantiza que impactos hechos en Gestor de Precios o Proveedores se reflejen.
        """
        super().showEvent(event)
        self.cargar_datos()

    def render_tabla_pagina(self, page_index):
        sl = self.paginacion.get_slice()
        productos_pagina = self.productos_db[sl]

        self.tabla.setRowCount(len(productos_pagina))
        for row, prod in enumerate(productos_pagina):
            self.tabla.setItem(row, 0, QTableWidgetItem(str(prod.id)))
            self.tabla.setItem(row, 1, QTableWidgetItem(prod.sku or ""))
            self.tabla.setItem(row, 2, QTableWidgetItem(prod.codigo_barras or ""))
            self.tabla.setItem(row, 3, QTableWidgetItem(prod.nombre))
            self.tabla.setItem(row, 4, QTableWidgetItem(f"{prod.stock_actual:.2f}"))
            self.tabla.setItem(row, 5, QTableWidgetItem(f"$ {prod.costo:.2f}"))
            self.tabla.setItem(row, 6, QTableWidgetItem(f"$ {prod.precio_minorista:.2f}"))

            # Guardamos el ID en el item para facilitar la edición
            self.tabla.item(row, 0).setData(Qt.ItemDataRole.UserRole, prod.id)

    def abrir_dialogo_nuevo(self):
        dialog = ProductoDialog(self)
        if dialog.exec():
            self.cargar_datos()

    def abrir_dialogo_editar(self):
        items = self.tabla.selectedItems()
        if not items:
            QMessageBox.information(self, "Selección", "Por favor seleccione un producto para editar.")
            return

        row = items[0].row()
        producto_id = self.tabla.item(row, 0).data(Qt.ItemDataRole.UserRole)
        producto = ProductoService.buscar_por_id(int(producto_id))

        if not producto:
            QMessageBox.warning(self, "Error", "No se encontró el producto en la BD.")
            return

        dialog = ProductoDialog(self, producto=producto)
        if dialog.exec():
            self.cargar_datos()
