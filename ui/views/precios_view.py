from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QComboBox, QRadioButton,
    QDoubleSpinBox, QMessageBox, QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from services.producto_service import ProductoService
from ui.components.pagination import PaginationWidget

class PreciosTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.productos_db = []
        self.filas_mostrar_totales = [] # Todas las filas filtradas

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

        self.btn_cargar_datos = QPushButton("Cargar Grilla Filtrada")

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

        self.paginacion = PaginationWidget(limit=50)
        self.paginacion.page_changed.connect(self.render_tabla_pagina)
        self.layout.addWidget(self.paginacion)

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

        self.filas_mostrar_totales = []
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
            margen_actual = ProductoService.calcular_margen_inverso(p.costo, p.precio_minorista)

            self.filas_mostrar_totales.append({
                'id': p.id,
                'sku': p.sku or "",
                'nombre': p.nombre,
                'costo': p.costo,
                'margen_actual': margen_actual,
                'precio_final_actual': p.precio_minorista,
                'ha_cambiado': False
            })

        self.paginacion.set_total_items(len(self.filas_mostrar_totales))
        self.btn_impactar.setEnabled(False) # Aún no hay cambios
        QMessageBox.information(self, "Carga Completa", f"Se cargaron {len(self.filas_mostrar_totales)} productos en el filtro actual.")

    def render_tabla_pagina(self, page_index):
        sl = self.paginacion.get_slice()
        datos_pagina = self.filas_mostrar_totales[sl]

        self.tabla.setRowCount(len(datos_pagina))
        color_resalte = QBrush(QColor(46, 125, 50, 80)) # Verde con alpha

        for r, data in enumerate(datos_pagina):
            item_id = QTableWidgetItem(str(data['id']))
            item_id.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            item_sku = QTableWidgetItem(data['sku'])
            item_sku.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            item_nom = QTableWidgetItem(data['nombre'])
            item_nom.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            item_costo = QTableWidgetItem(f"$ {data['costo']:.2f}")
            item_costo.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            item_margen = QTableWidgetItem(f"{data['margen_actual']:.2f} %")
            item_margen.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            item_pf = QTableWidgetItem(f"$ {data['precio_final_actual']:.2f}")
            item_pf.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            if data['ha_cambiado']:
                item_margen.setBackground(color_resalte)
                item_pf.setBackground(color_resalte)

            self.tabla.setItem(r, 0, item_id)
            self.tabla.setItem(r, 1, item_sku)
            self.tabla.setItem(r, 2, item_nom)
            self.tabla.setItem(r, 3, item_costo)
            self.tabla.setItem(r, 4, item_margen)
            self.tabla.setItem(r, 5, item_pf)

    def previsualizar_calculo(self):
        if not self.filas_mostrar_totales:
            QMessageBox.warning(self, "Error", "La grilla está vacía. Cargue datos primero.")
            return

        margen_usuario = self.spin_margen.value()

        # Iterar sobre TODAS las filas filtradas (en memoria) para recalcular
        hay_cambios = False
        for data in self.filas_mostrar_totales:
            costo = data['costo']
            pf_ant = data['precio_final_actual']

            # Calcular nuevo precio con el Service (que ya incluye redondeo de negocio)
            try:
                pf_nuevo = ProductoService.calcular_precio_final(costo, margen_usuario)
            except ValueError:
                continue

            if abs(pf_nuevo - pf_ant) > 0.01:
                data['margen_actual'] = margen_usuario
                data['precio_final_actual'] = pf_nuevo
                data['ha_cambiado'] = True
                hay_cambios = True

        # Re-renderizar la página actual para reflejar cambios
        self.render_tabla_pagina(self.paginacion.current_page)

        if hay_cambios:
            self.btn_impactar.setEnabled(True)

    def impactar_db(self):
        # Solamente tomar las filas que cambiaron dentro del subset filtrado
        actualizaciones = [
            {'id': d['id'], 'precio_minorista': d['precio_final_actual']}
            for d in self.filas_mostrar_totales if d['ha_cambiado']
        ]

        if not actualizaciones:
            QMessageBox.information(self, "Sin cambios", "No hay cambios para guardar.")
            return

        reply = QMessageBox.question(
            self, "Confirmación Crítica",
            f"Se actualizarán {len(actualizaciones)} precios finales en la base de datos de SQLite.\n¿Proceder?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                afectados = ProductoService.actualizar_precios_masivo(actualizaciones)
                QMessageBox.information(self, "Transacción Exitosa", f"Se aplicaron los nuevos precios a {afectados} productos.")
                self.btn_impactar.setEnabled(False)
                # Recargar para limpiar estilos
                self.cargar_grilla()
            except Exception as e:
                QMessageBox.critical(self, "Error Transaccional", f"La base de datos bloqueó la operación:\n{str(e)}")
