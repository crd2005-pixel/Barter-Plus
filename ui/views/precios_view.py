from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QComboBox, QRadioButton,
    QDoubleSpinBox, QMessageBox, QGroupBox, QFormLayout, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from services.producto_service import ProductoService
from ui.components.pagination import PaginationWidget

class MotorPreciosTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.productos_db = []
        self.filas_mostrar_totales = [] # Todas las filas filtradas

        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # Contenedor superior (Filtros y Motor)
        self.top_widget = QWidget()
        from PyQt6.QtWidgets import QSizePolicy
        self.top_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.top_layout = QVBoxLayout(self.top_widget)
        self.top_layout.setContentsMargins(0, 0, 0, 0)

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
        self.top_layout.addWidget(self.filtros_group)

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
        self.top_layout.addWidget(self.motor_group)

        # Contenedor inferior (Grilla y Paginación)
        self.bottom_widget = QWidget()
        self.bottom_layout = QVBoxLayout(self.bottom_widget)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)

        # --- ZONA DE PREVISUALIZACIÓN ---
        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels([
            "ID BD", "SKU Interno", "Nombre", "Costo Base (PM)", "Margen %", "Precio Final"
        ])

        # Ergonomía: Columnas interactivas
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setColumnWidth(0, 50)
        self.tabla.setColumnWidth(1, 120)
        self.tabla.setColumnWidth(2, 300)
        self.tabla.setColumnWidth(3, 120)
        self.tabla.setColumnWidth(4, 100)

        self.tabla.setAlternatingRowColors(True)
        self.bottom_layout.addWidget(self.tabla)

        self.paginacion = PaginationWidget(limit=50)
        self.paginacion.page_changed.connect(self.render_tabla_pagina)
        self.bottom_layout.addWidget(self.paginacion)

        self.splitter.addWidget(self.top_widget)
        self.splitter.addWidget(self.bottom_widget)
        # 30% top, 70% grid
        self.splitter.setSizes([200, 500])

        self.layout.addWidget(self.splitter)

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

    def showEvent(self, event):
        """
        Sincronización de Estado:
        Auto-refresco al abrir la pestaña para tomar cambios de otras pestañas.
        """
        super().showEvent(event)
        self.recargar_memoria()
        self.actualizar_combo_filtros()
        # Si la tabla ya estaba cargada, la recargamos con el filtro activo
        if self.tabla.rowCount() > 0:
            self.cargar_grilla()

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


class CodigosBarraTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        # 1. Configuración de Hardware
        from PyQt6.QtWidgets import QGroupBox, QFormLayout, QLineEdit, QPushButton, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
        from PyQt6.QtCore import QSettings
        from services.producto_service import ProductoService

        group_hw = QGroupBox("Configuración de Hardware")
        form_hw = QFormLayout(group_hw)

        self.txt_imp_eti = QLineEdit()
        self.txt_imp_eti.setPlaceholderText("Ej: Xprinter XP-58")
        self.txt_imp_tic = QLineEdit()
        self.txt_imp_tic.setPlaceholderText("Ej: Xprinter XP-58")

        self.settings = QSettings("BarterPlus", "HardwareConfig")
        self.txt_imp_eti.setText(str(self.settings.value("printer_etiquetas", "")))
        self.txt_imp_tic.setText(str(self.settings.value("printer_tickets", "")))

        form_hw.addRow("Impresora de Etiquetas:", self.txt_imp_eti)
        form_hw.addRow("Impresora de Tickets:", self.txt_imp_tic)

        btn_hw = QPushButton("Guardar Configuración")
        btn_hw.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        btn_hw.clicked.connect(self.guardar_hw)
        form_hw.addRow("", btn_hw)

        self.layout.addWidget(group_hw)

        # 2. Generador Automático
        group_gen = QGroupBox("Generador de Códigos")
        lay_gen = QHBoxLayout(group_gen)
        btn_gen = QPushButton("Generar Códigos Faltantes")
        btn_gen.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; padding: 10px;")
        btn_gen.clicked.connect(self.generar_codigos)
        lay_gen.addWidget(btn_gen)
        lay_gen.addStretch()

        self.layout.addWidget(group_gen)

        # 3. Grilla de Impresión en Lote
        group_lote = QGroupBox("Grilla de Impresión en Lote")
        lay_lote = QVBoxLayout(group_lote)

        self.btn_imprimir = QPushButton("Imprimir Lote Seleccionado")
        self.btn_imprimir.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; padding: 10px;")
        self.btn_imprimir.clicked.connect(self.imprimir_lote)

        lay_lote.addWidget(self.btn_imprimir)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["ID", "Código", "Nombre", "Equivalencias", "Precio"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Editables sólo las equivalencias
        self.tabla.itemChanged.connect(self.guardar_equivalencia)

        lay_lote.addWidget(self.tabla)
        self.layout.addWidget(group_lote)

        self.cargar_datos()

    def guardar_hw(self):
        from PyQt6.QtWidgets import QMessageBox
        self.settings.setValue("printer_etiquetas", self.txt_imp_eti.text().strip())
        self.settings.setValue("printer_tickets", self.txt_imp_tic.text().strip())
        QMessageBox.information(self, "Configuración", "Configuración de hardware guardada.")

    def generar_codigos(self):
        from database.conexion import get_session
        from database.models.producto import Producto
        from PyQt6.QtWidgets import QMessageBox

        count = 0
        with get_session() as session:
            prods = session.query(Producto).all()
            for p in prods:
                if not p.codigo_barras or not p.codigo_barras.strip():
                    p.codigo_barras = f"BP-{p.id:05d}"
                    count += 1
            session.commit()

        if count > 0:
            QMessageBox.information(self, "Éxito", f"Se generaron {count} códigos nuevos.")
            self.cargar_datos()
        else:
            QMessageBox.information(self, "Aviso", "No se encontraron productos sin código de barras.")

    def cargar_datos(self):
        from services.producto_service import ProductoService
        from PyQt6.QtWidgets import QTableWidgetItem
        from PyQt6.QtCore import Qt

        self.tabla.blockSignals(True)
        prods = ProductoService.listar_todos()
        self.tabla.setRowCount(len(prods))

        for r, p in enumerate(prods):
            i_id = QTableWidgetItem(str(p.id))
            i_id.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.tabla.setItem(r, 0, i_id)

            codigo = p.codigo_proveedor or p.codigo_barras or f"INT{p.id:06d}"
            i_cod = QTableWidgetItem(codigo)
            i_cod.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.tabla.setItem(r, 1, i_cod)

            i_nom = QTableWidgetItem(p.nombre)
            i_nom.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.tabla.setItem(r, 2, i_nom)

            i_eq = QTableWidgetItem(getattr(p, 'equivalencias', '') or '')
            self.tabla.setItem(r, 3, i_eq)

            i_pre = QTableWidgetItem(f"$ {p.precio_minorista:.2f}")
            i_pre.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.tabla.setItem(r, 4, i_pre)

        self.tabla.blockSignals(False)

    def guardar_equivalencia(self, item):
        col = item.column()
        row = item.row()
        if col == 3:
            from database.conexion import get_session
            from database.models.producto import Producto
            prod_id = int(self.tabla.item(row, 0).text())
            nuevo_val = item.text().strip()

            with get_session() as session:
                prod = session.get(Producto, prod_id)
                if prod:
                    prod.equivalencias = nuevo_val
                    session.commit()

    def imprimir_lote(self):
        from PyQt6.QtWidgets import QMessageBox
        from services.printer_service import PrinterService

        items = self.tabla.selectedItems()
        if not items:
            QMessageBox.warning(self, "Impresión", "Seleccione al menos una fila.")
            return

        filas = set(i.row() for i in items)

        try:
            for row in filas:
                prod_id = int(self.tabla.item(row, 0).text())
                PrinterService.imprimir_etiqueta(prod_id)
            QMessageBox.information(self, "Impresión", f"Lote de {len(filas)} etiquetas enviado a la impresora.")
        except Exception as e:
            QMessageBox.critical(self, "Error de Impresión", str(e))


class PreciosTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        from PyQt6.QtWidgets import QTabWidget
        self.tabs = QTabWidget()

        self.tab_motor = MotorPreciosTab()
        self.tab_codigos = CodigosBarraTab()

        self.tabs.addTab(self.tab_motor, "Motor de Precios")
        self.tabs.addTab(self.tab_codigos, "Códigos de Barra y Etiquetas")

        layout.addWidget(self.tabs)
