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
        self._cache_datos = []

        # 1. Configuración de Hardware Avanzada
        from PyQt6.QtWidgets import QGroupBox, QFormLayout, QLineEdit, QPushButton, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout, QDoubleSpinBox, QCheckBox
        from PyQt6.QtCore import QSettings, Qt
        from services.producto_service import ProductoService

        group_hw = QGroupBox("Configuración de Hardware y Etiqueta")
        form_hw = QFormLayout(group_hw)

        self.txt_imp_eti = QLineEdit()
        self.txt_imp_eti.setPlaceholderText("Ej: Xprinter XP-58")
        self.txt_imp_tic = QLineEdit()
        self.txt_imp_tic.setPlaceholderText("Ej: Xprinter XP-58")

        # Dimensiones
        lay_dim = QHBoxLayout()
        self.sp_width = QDoubleSpinBox()
        self.sp_width.setRange(10, 300)
        self.sp_width.setSuffix(" mm")
        self.sp_height = QDoubleSpinBox()
        self.sp_height.setRange(10, 300)
        self.sp_height.setSuffix(" mm")

        self.sp_off_x = QDoubleSpinBox()
        self.sp_off_x.setRange(-50, 50)
        self.sp_off_x.setSuffix(" mm")
        self.sp_off_y = QDoubleSpinBox()
        self.sp_off_y.setRange(-50, 50)
        self.sp_off_y.setSuffix(" mm")

        lay_dim.addWidget(QLabel("Ancho:"))
        lay_dim.addWidget(self.sp_width)
        lay_dim.addWidget(QLabel("Alto:"))
        lay_dim.addWidget(self.sp_height)
        lay_dim.addWidget(QLabel("Off X:"))
        lay_dim.addWidget(self.sp_off_x)
        lay_dim.addWidget(QLabel("Off Y:"))
        lay_dim.addWidget(self.sp_off_y)

        self.settings = QSettings("BarterPlus", "HardwareConfig")
        self.txt_imp_eti.setText(str(self.settings.value("printer_etiquetas", "")))
        self.txt_imp_tic.setText(str(self.settings.value("printer_tickets", "")))
        self.sp_width.setValue(float(self.settings.value("eti_w", 50.0)))
        self.sp_height.setValue(float(self.settings.value("eti_h", 25.0)))
        self.sp_off_x.setValue(float(self.settings.value("eti_off_x", 0.0)))
        self.sp_off_y.setValue(float(self.settings.value("eti_off_y", 0.0)))

        form_hw.addRow("Impresora de Etiquetas:", self.txt_imp_eti)
        form_hw.addRow("Impresora de Tickets:", self.txt_imp_tic)
        form_hw.addRow("Dimensiones Térmicas:", lay_dim)

        btn_hw = QPushButton("Guardar Configuración")
        btn_hw.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        btn_hw.clicked.connect(self.guardar_hw)
        form_hw.addRow("", btn_hw)

        self.layout.addWidget(group_hw)

        # 2. Generador Automático y Buscador
        group_gen = QGroupBox("Base de Datos de Códigos")
        lay_gen = QHBoxLayout(group_gen)

        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Buscar por Nombre o Código...")
        self.txt_buscar.textChanged.connect(self.filtrar_datos)

        btn_gen = QPushButton("Generar Códigos Faltantes")
        btn_gen.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; padding: 10px;")
        btn_gen.clicked.connect(self.generar_codigos)

        self.btn_imprimir = QPushButton("Imprimir Selección (Spool)")
        self.btn_imprimir.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; padding: 10px;")
        self.btn_imprimir.clicked.connect(self.imprimir_lote)

        lay_gen.addWidget(self.txt_buscar)
        lay_gen.addWidget(btn_gen)
        lay_gen.addWidget(self.btn_imprimir)

        self.layout.addWidget(group_gen)

        # 3. Grilla Multiselección
        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(["Sel.", "ID", "Código", "Nombre", "Equivalencias", "Precio"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        self.tabla.itemChanged.connect(self.guardar_equivalencia)

        self.layout.addWidget(self.tabla)
        self.cargar_datos()

    def guardar_hw(self):
        from PyQt6.QtWidgets import QMessageBox
        self.settings.setValue("printer_etiquetas", self.txt_imp_eti.text().strip())
        self.settings.setValue("printer_tickets", self.txt_imp_tic.text().strip())
        self.settings.setValue("eti_w", self.sp_width.value())
        self.settings.setValue("eti_h", self.sp_height.value())
        self.settings.setValue("eti_off_x", self.sp_off_x.value())
        self.settings.setValue("eti_off_y", self.sp_off_y.value())
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

        self._cache_datos = ProductoService.listar_todos()
        self._render_grilla(self._cache_datos)

    def _render_grilla(self, lista):
        from PyQt6.QtWidgets import QTableWidgetItem
        from PyQt6.QtCore import Qt

        self.tabla.blockSignals(True)
        self.tabla.setRowCount(len(lista))

        for r, p in enumerate(lista):
            # Checkbox
            ck = QTableWidgetItem()
            ck.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            ck.setCheckState(Qt.CheckState.Unchecked)
            self.tabla.setItem(r, 0, ck)

            i_id = QTableWidgetItem(str(p.id))
            i_id.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.tabla.setItem(r, 1, i_id)

            codigo = p.codigo_proveedor or p.codigo_barras or f"INT{p.id:06d}"
            i_cod = QTableWidgetItem(codigo)
            i_cod.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.tabla.setItem(r, 2, i_cod)

            i_nom = QTableWidgetItem(p.nombre)
            i_nom.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.tabla.setItem(r, 3, i_nom)

            i_eq = QTableWidgetItem(getattr(p, 'equivalencias', '') or '')
            self.tabla.setItem(r, 4, i_eq)

            i_pre = QTableWidgetItem(f"$ {p.precio_minorista:.2f}")
            i_pre.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.tabla.setItem(r, 5, i_pre)

        self.tabla.blockSignals(False)

    def filtrar_datos(self):
        txt = self.txt_buscar.text().lower()
        if not txt:
            self._render_grilla(self._cache_datos)
            return

        filtrados = []
        for p in self._cache_datos:
            codigo = (p.codigo_proveedor or p.codigo_barras or "").lower()
            if txt in p.nombre.lower() or txt in codigo:
                filtrados.append(p)

        self._render_grilla(filtrados)

    def guardar_equivalencia(self, item):
        col = item.column()
        row = item.row()
        if col == 4:
            from database.conexion import get_session
            from database.models.producto import Producto
            prod_id = int(self.tabla.item(row, 1).text())
            nuevo_val = item.text().strip()

            with get_session() as session:
                prod = session.get(Producto, prod_id)
                if prod:
                    prod.equivalencias = nuevo_val
                    session.commit()
            # Update cache instead of doing a full reload
            for p in self._cache_datos:
                if p.id == prod_id:
                    p.equivalencias = nuevo_val
                    break

    def imprimir_lote(self):
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtCore import Qt
        from ui.components.printer.codigos_barra import EtiquetasPreviewDialog
        from database.models.producto import Producto
        from database.conexion import get_session

        seleccionados = []
        for r in range(self.tabla.rowCount()):
            if self.tabla.item(r, 0).checkState() == Qt.CheckState.Checked:
                seleccionados.append(int(self.tabla.item(r, 1).text()))

        if not seleccionados:
            QMessageBox.warning(self, "Impresión", "Seleccione al menos un producto usando los checkboxes.")
            return

        items = []
        try:
            with get_session() as session:
                for prod_id in seleccionados:
                    p = session.get(Producto, prod_id)
                    if p:
                        codigo = p.codigo_proveedor or p.codigo_barras or f"INT{p.id:06d}"
                        items.append({
                            "id": p.id,
                            "marca": p.marca.nombre if p.marca else "",
                            "nombre": p.nombre,
                            "code": codigo,
                            "equivalencia": getattr(p, 'equivalencias', ''),
                            "sku": p.sku,
                            "cod_prov": p.codigo_proveedor,
                            "precio": p.precio_minorista
                        })

            if items:
                dlg = EtiquetasPreviewDialog(items, self)
                dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error al generar vista previa", str(e))

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
