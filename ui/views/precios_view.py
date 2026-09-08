from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QComboBox, QRadioButton,
    QDoubleSpinBox, QMessageBox, QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from services.producto_service import ProductoService

class PreciosTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.productos_db = []

        # --- ZONA DE FILTROS ---
        self.filtros_group = QGroupBox("Carga y Filtros de Productos")
        self.filtros_layout = QHBoxLayout()

        self.radio_masivo = QRadioButton("Todos (Masivo)")
        self.radio_masivo.setChecked(True)
        self.radio_proveedor = QRadioButton("Por Proveedor")
        self.radio_rubro = QRadioButton("Por Categoría")
        self.radio_marca = QRadioButton("Por Marca")

        self.combo_filtro_valor = QComboBox()
        self.combo_filtro_valor.setEnabled(False)
        self.combo_filtro_valor.setMinimumWidth(200)

        self.btn_cargar_datos = QPushButton("Cargar Grilla")

        self.filtros_layout.addWidget(self.radio_masivo)
        self.filtros_layout.addWidget(self.radio_proveedor)
        self.filtros_layout.addWidget(self.radio_rubro)
        self.filtros_layout.addWidget(self.radio_marca)
        self.filtros_layout.addWidget(QLabel("Valor:"))
        self.filtros_layout.addWidget(self.combo_filtro_valor)
        self.filtros_layout.addStretch()
        self.filtros_layout.addWidget(self.btn_cargar_datos)

        self.filtros_group.setLayout(self.filtros_layout)
        self.layout.addWidget(self.filtros_group)

        # --- MOTOR DE MÁRGENES ---
        self.motor_group = QGroupBox("Motor de Márgenes")
        self.motor_layout = QHBoxLayout()

        self.spin_margen = QDoubleSpinBox()
        self.spin_margen.setRange(0, 99.99)
        self.spin_margen.setValue(30.0)
        self.spin_margen.setSuffix(" %")

        self.btn_calcular = QPushButton("Previsualizar Cálculo")
        self.btn_calcular.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")

        self.motor_layout.addWidget(QLabel("Margen_Usuario a Aplicar:"))
        self.motor_layout.addWidget(self.spin_margen)
        self.motor_layout.addWidget(self.btn_calcular)
        self.motor_layout.addStretch()

        self.motor_group.setLayout(self.motor_layout)
        self.layout.addWidget(self.motor_group)

        # --- ZONA DE PREVISUALIZACIÓN ---
        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels([
            "ID BD", "SKU Interno", "Nombre", "Costo Base (PM)", "Margen %", "Precio Final"
        ])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.setAlternatingRowColors(True)
        self.layout.addWidget(self.tabla)

        # --- ACCIONES FINALES ---
        self.acciones_layout = QHBoxLayout()
        self.btn_impactar = QPushButton("Impactar Precios Finales")
        self.btn_impactar.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 10px;")
        self.btn_impactar.setEnabled(False)

        self.acciones_layout.addStretch()
        self.acciones_layout.addWidget(self.btn_impactar)
        self.layout.addLayout(self.acciones_layout)

        # --- CONEXIONES ---
        self.radio_masivo.toggled.connect(self.actualizar_combo_filtros)
        self.radio_proveedor.toggled.connect(self.actualizar_combo_filtros)
        self.radio_rubro.toggled.connect(self.actualizar_combo_filtros)
        self.radio_marca.toggled.connect(self.actualizar_combo_filtros)

        self.btn_cargar_datos.clicked.connect(self.cargar_grilla)
        self.btn_calcular.clicked.connect(self.previsualizar_calculo)
        self.btn_impactar.clicked.connect(self.impactar_db)

        # Cargar catálogo a memoria
        self.recargar_memoria()

    def recargar_memoria(self):
        self.productos_db = ProductoService.listar_todos()

    def actualizar_combo_filtros(self):
        self.combo_filtro_valor.clear()

        if self.radio_masivo.isChecked():
            self.combo_filtro_valor.setEnabled(False)
            return

        self.combo_filtro_valor.setEnabled(True)

        # Usar la memoria cacheada para armar opciones
        valores = set()
        for p in self.productos_db:
            if self.radio_proveedor.isChecked() and p.proveedor:
                valores.add(p.proveedor.nombre)
            elif self.radio_rubro.isChecked() and p.categoria:
                valores.add(p.categoria.nombre)
            elif self.radio_marca.isChecked() and p.marca:
                valores.add(p.marca.nombre)

        self.combo_filtro_valor.addItems(sorted(list(valores)))

    def cargar_grilla(self):
        # Refresh de memoria por si hubo cambios en otras pestañas
        self.recargar_memoria()

        filas_mostrar = []
        filtro_val = self.combo_filtro_valor.currentText()

        for p in self.productos_db:
            # Lógica de exclusión por filtro
            if self.radio_proveedor.isChecked():
                if not p.proveedor or p.proveedor.nombre != filtro_val: continue
            elif self.radio_rubro.isChecked():
                if not p.categoria or p.categoria.nombre != filtro_val: continue
            elif self.radio_marca.isChecked():
                if not p.marca or p.marca.nombre != filtro_val: continue

            # Calcular margen actual para mostrar
            margen_actual = ProductoService.calcular_margen_inverso(p.costo, p.iva, p.precio_minorista)

            filas_mostrar.append({
                'id': p.id,
                'sku': p.sku or "",
                'nombre': p.nombre,
                'costo': p.costo,
                'iva': p.iva,
                'margen_actual': margen_actual,
                'precio_final_actual': p.precio_minorista
            })

        self.tabla.setRowCount(len(filas_mostrar))
        for r, data in enumerate(filas_mostrar):
            for c in range(6):
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.tabla.setItem(r, c, item)

            self.tabla.item(r, 0).setText(str(data['id']))
            self.tabla.item(r, 1).setText(data['sku'])
            self.tabla.item(r, 2).setText(data['nombre'])

            # Guardamos el IVA en el UserRole del costo para cálculos futuros
            item_costo = self.tabla.item(r, 3)
            item_costo.setText(f"{data['costo']:.2f}")
            item_costo.setData(Qt.ItemDataRole.UserRole, data['iva'])

            self.tabla.item(r, 4).setText(f"{data['margen_actual']:.2f}")
            self.tabla.item(r, 5).setText(f"{data['precio_final_actual']:.2f}")

        self.btn_impactar.setEnabled(False) # Aún no hay cambios
        QMessageBox.information(self, "Carga Completa", f"Se cargaron {len(filas_mostrar)} productos en la grilla.")

    def previsualizar_calculo(self):
        if self.tabla.rowCount() == 0:
            QMessageBox.warning(self, "Error", "La grilla está vacía. Cargue datos primero.")
            return

        margen_usuario = self.spin_margen.value()

        # Definir color de resalte sutil (Verde claro para tema oscuro, cambiaremos si es necesario)
        color_resalte = QBrush(QColor(46, 125, 50, 80)) # Verde con alpha

        for r in range(self.tabla.rowCount()):
            try:
                # Obtener costo e IVA de la tabla
                costo = float(self.tabla.item(r, 3).text().replace(',', '.'))
                iva = self.tabla.item(r, 3).data(Qt.ItemDataRole.UserRole)

                # Obtener precio final anterior para comparar
                pf_ant = float(self.tabla.item(r, 5).text().replace(',', '.'))

                # Calcular nuevo precio
                pf_nuevo = ProductoService.calcular_precio_final(costo, iva, margen_usuario)

                # Actualizar celdas
                item_margen = self.tabla.item(r, 4)
                item_pf = self.tabla.item(r, 5)

                item_margen.setText(f"{margen_usuario:.2f}")
                item_pf.setText(f"{pf_nuevo:.2f}")

                # Resaltar si cambió
                if abs(pf_nuevo - pf_ant) > 0.01:
                    item_margen.setBackground(color_resalte)
                    item_pf.setBackground(color_resalte)

            except ValueError:
                continue

        self.btn_impactar.setEnabled(True)

    def impactar_db(self):
        reply = QMessageBox.question(
            self, "Confirmación Crítica",
            "Se actualizarán todos los precios previsualizados en la base de datos de SQLite.\n¿Proceder?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            actualizaciones = []
            for r in range(self.tabla.rowCount()):
                try:
                    pid = int(self.tabla.item(r, 0).text())
                    pf_nuevo = float(self.tabla.item(r, 5).text().replace(',', '.'))

                    actualizaciones.append({
                        'id': pid,
                        'precio_minorista': pf_nuevo
                    })
                except Exception:
                    continue

            try:
                afectados = ProductoService.actualizar_precios_masivo(actualizaciones)
                QMessageBox.information(self, "Transacción Exitosa", f"Se aplicaron los nuevos precios a {afectados} productos.")
                self.btn_impactar.setEnabled(False)
                # Recargar para limpiar estilos
                self.cargar_grilla()
            except Exception as e:
                QMessageBox.critical(self, "Error Transaccional", f"La base de datos bloqueó la operación:\n{str(e)}")
