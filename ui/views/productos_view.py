from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QLabel, QFormLayout, QMessageBox, QDoubleSpinBox, QComboBox
)
from PyQt6.QtCore import Qt
from services.producto_service import ProductoService

class ProductoDialog(QDialog):
    def __init__(self, parent=None, producto_id=None):
        super().__init__(parent)
        self.producto_id = producto_id
        self.setWindowTitle("Nuevo Producto" if not producto_id else "Editar Producto")
        self.resize(400, 300)

        self.layout = QFormLayout(self)

        self.nombre_input = QLineEdit()
        self.codigo_input = QLineEdit()

        self.costo_input = QDoubleSpinBox()
        self.costo_input.setMaximum(9999999.99)
        self.costo_input.setDecimals(2)

        self.margen_input = QDoubleSpinBox()
        self.margen_input.setMaximum(99.99) # Margen no puede ser >= 100
        self.margen_input.setDecimals(2)
        self.margen_input.setValue(30.0) # Margen default 30%

        self.precio_final_label = QLabel("$ 0.00")
        self.precio_final_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.layout.addRow("Nombre:", self.nombre_input)
        self.layout.addRow("Código de Barras:", self.codigo_input)
        self.layout.addRow("Costo:", self.costo_input)
        self.layout.addRow("Margen (%):", self.margen_input)
        self.layout.addRow("Precio Final Sugerido:", self.precio_final_label)

        # Conectar señales para cálculo en tiempo real
        self.costo_input.valueChanged.connect(self.recalcular_precio)
        self.margen_input.valueChanged.connect(self.recalcular_precio)

        # Botones
        self.btn_layout = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar")
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_layout.addWidget(self.btn_guardar)
        self.btn_layout.addWidget(self.btn_cancelar)

        self.layout.addRow(self.btn_layout)

        self.btn_guardar.clicked.connect(self.guardar)
        self.btn_cancelar.clicked.connect(self.reject)

        self.cargar_datos()

    def recalcular_precio(self):
        costo = self.costo_input.value()
        margen = self.margen_input.value()
        try:
            # Asumimos 21% de IVA por defecto para el cálculo rápido visual
            pf = ProductoService.calcular_precio_final(costo, 21.0, margen)
            self.precio_final_label.setText(f"$ {pf:.2f}")
        except ValueError:
            self.precio_final_label.setText("Error (Margen >= 100%)")

    def cargar_datos(self):
        if self.producto_id:
            prod = ProductoService.buscar_por_id(self.producto_id)
            if prod:
                self.nombre_input.setText(prod.nombre)
                self.codigo_input.setText(prod.codigo_barras or "")
                self.costo_input.setValue(prod.costo)
                # Estimamos un margen si quisieramos, por simplicidad lo dejamos en default o requeriría un campo margen en bd.
                self.recalcular_precio()

    def guardar(self):
        nombre = self.nombre_input.text().strip()
        codigo = self.codigo_input.text().strip()
        costo = self.costo_input.value()

        if not nombre:
            QMessageBox.warning(self, "Error", "El nombre es obligatorio.")
            return

        try:
            if not self.producto_id:
                nuevo = ProductoService.crear_producto(
                    nombre=nombre,
                    costo=costo,
                    codigo_barras=codigo if codigo else None
                )
                ProductoService.actualizar_precio(nuevo.id, self.margen_input.value())
            else:
                # Logica de edición asumiendo que actualizaríamos
                pass

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))


class ProductosTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        # --- Barra superior (Buscador y Acciones) ---
        self.top_bar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por nombre, código...")
        self.search_input.setMinimumWidth(300)
        self.search_input.textChanged.connect(self.cargar_tabla)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self.cargar_tabla)

        self.btn_nuevo = QPushButton("Nuevo Producto")
        self.btn_editar = QPushButton("Editar")
        self.btn_eliminar = QPushButton("Eliminar (Deshabilitado)")
        self.btn_eliminar.setEnabled(False) # Por seguridad

        self.top_bar.addWidget(self.search_input)
        self.top_bar.addWidget(self.btn_buscar)
        self.top_bar.addStretch()
        self.top_bar.addWidget(self.btn_nuevo)
        self.top_bar.addWidget(self.btn_editar)
        self.top_bar.addWidget(self.btn_eliminar)

        self.layout.addLayout(self.top_bar)

        # --- Tabla de Productos ---
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["ID", "Cód. Barras", "Nombre", "Costo", "Precio Final"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.layout.addWidget(self.tabla)

        # --- Conexiones ---
        self.btn_nuevo.clicked.connect(self.abrir_dialogo_nuevo)
        self.btn_editar.clicked.connect(self.abrir_dialogo_editar)

        # Cargar datos iniciales
        self.cargar_tabla()

    def cargar_tabla(self):
        busqueda = self.search_input.text().strip()
        productos = ProductoService.listar_todos(busqueda)

        self.tabla.setRowCount(len(productos))
        for row, prod in enumerate(productos):
            self.tabla.setItem(row, 0, QTableWidgetItem(str(prod.id)))
            self.tabla.setItem(row, 1, QTableWidgetItem(prod.codigo_barras or ""))
            self.tabla.setItem(row, 2, QTableWidgetItem(prod.nombre))
            self.tabla.setItem(row, 3, QTableWidgetItem(f"${prod.costo:.2f}"))
            self.tabla.setItem(row, 4, QTableWidgetItem(f"${prod.precio_minorista:.2f}"))

            # Guardamos el ID en el item para facilitar la edición
            self.tabla.item(row, 0).setData(Qt.ItemDataRole.UserRole, prod.id)

    def abrir_dialogo_nuevo(self):
        dialog = ProductoDialog(self)
        if dialog.exec():
            self.cargar_tabla()

    def abrir_dialogo_editar(self):
        # Obtener ID seleccionado
        items = self.tabla.selectedItems()
        if not items:
            QMessageBox.information(self, "Selección", "Por favor seleccione un producto para editar.")
            return

        row = items[0].row()
        producto_id = self.tabla.item(row, 0).data(Qt.ItemDataRole.UserRole)

        dialog = ProductoDialog(self, producto_id=producto_id)
        if dialog.exec():
            self.cargar_tabla()
