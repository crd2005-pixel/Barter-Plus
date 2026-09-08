import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QComboBox, QRadioButton, QDoubleSpinBox, QMessageBox,
    QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt
from services.producto_service import ProductoService

class PreciosTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.df = None # Pandas DataFrame en memoria
        self.productos_db = [] # Cache de productos de la BD

        # --- ZONA DE CARGA ---
        self.carga_layout = QHBoxLayout()
        self.btn_importar = QPushButton("Importar Excel/CSV")
        self.lbl_archivo = QLabel("Ningún archivo cargado")

        self.carga_layout.addWidget(self.btn_importar)
        self.carga_layout.addWidget(self.lbl_archivo)
        self.carga_layout.addStretch()
        self.layout.addLayout(self.carga_layout)

        # --- ZONA DE FILTROS Y MAPEO ---
        self.mapeo_group = QGroupBox("Mapeo de Columnas")
        self.mapeo_layout = QHBoxLayout()

        self.combo_codigo = QComboBox()
        self.combo_costo = QComboBox()
        self.combo_proveedor = QComboBox()
        self.combo_rubro = QComboBox()
        self.combo_marca = QComboBox()

        self.mapeo_layout.addWidget(QLabel("Cód. Barras/SKU:"))
        self.mapeo_layout.addWidget(self.combo_codigo)
        self.mapeo_layout.addWidget(QLabel("Costo Nuevo:"))
        self.mapeo_layout.addWidget(self.combo_costo)

        # Agregamos mapeo de filtros
        self.mapeo_layout.addWidget(QLabel("Proveedor:"))
        self.mapeo_layout.addWidget(self.combo_proveedor)
        self.mapeo_layout.addWidget(QLabel("Rubro:"))
        self.mapeo_layout.addWidget(self.combo_rubro)
        self.mapeo_layout.addWidget(QLabel("Marca:"))
        self.mapeo_layout.addWidget(self.combo_marca)

        self.mapeo_group.setLayout(self.mapeo_layout)
        self.layout.addWidget(self.mapeo_group)
        self.mapeo_group.setEnabled(False) # Se habilita tras cargar

        # --- ZONA DE AUMENTOS (Core) ---
        self.aumentos_group = QGroupBox("Opciones de Aumento / Margen")
        self.aumentos_layout = QFormLayout()

        self.tipo_aumento_layout = QHBoxLayout()
        self.radio_masivo = QRadioButton("Masivo")
        self.radio_masivo.setChecked(True)
        self.radio_proveedor = QRadioButton("Por Proveedor")
        self.radio_rubro = QRadioButton("Por Rubro")
        self.radio_marca = QRadioButton("Por Marca")

        self.tipo_aumento_layout.addWidget(self.radio_masivo)
        self.tipo_aumento_layout.addWidget(self.radio_proveedor)
        self.tipo_aumento_layout.addWidget(self.radio_rubro)
        self.tipo_aumento_layout.addWidget(self.radio_marca)
        self.tipo_aumento_layout.addStretch()

        # Valor a filtrar (Ej: "WEG" si es por proveedor)
        self.filtro_valor_layout = QHBoxLayout()
        self.combo_filtro_valor = QComboBox()
        self.combo_filtro_valor.setEnabled(False)
        self.filtro_valor_layout.addWidget(QLabel("Seleccionar:"))
        self.filtro_valor_layout.addWidget(self.combo_filtro_valor)
        self.filtro_valor_layout.addStretch()

        self.spin_margen = QDoubleSpinBox()
        self.spin_margen.setRange(0, 99.99)
        self.spin_margen.setValue(30.0)

        self.btn_calcular = QPushButton("Aplicar Cálculo (Preview)")

        self.aumentos_layout.addRow("Tipo de Aumento:", self.tipo_aumento_layout)
        self.aumentos_layout.addRow("Filtro:", self.filtro_valor_layout)
        self.aumentos_layout.addRow("Margen a Aplicar (%):", self.spin_margen)
        self.aumentos_layout.addRow("", self.btn_calcular)

        self.aumentos_group.setLayout(self.aumentos_layout)
        self.layout.addWidget(self.aumentos_group)

        # --- ZONA DE PREVISUALIZACIÓN ---
        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels([
            "ID BD", "Nombre", "Costo Anterior", "Costo Nuevo", "Margen %", "Precio Final"
        ])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.layout.addWidget(self.tabla)

        # --- ACCIONES FINALES ---
        self.acciones_layout = QHBoxLayout()
        self.btn_impactar = QPushButton("Impactar en Base de Datos")
        self.btn_exportar = QPushButton("Exportar a Excel")

        self.btn_impactar.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.btn_exportar.setStyleSheet("background-color: #1565c0; color: white; font-weight: bold;")

        self.btn_impactar.setEnabled(False)
        self.btn_exportar.setEnabled(False)

        self.acciones_layout.addStretch()
        self.acciones_layout.addWidget(self.btn_exportar)
        self.acciones_layout.addWidget(self.btn_impactar)
        self.layout.addLayout(self.acciones_layout)

        # --- CONEXIONES ---
        self.btn_importar.clicked.connect(self.cargar_archivo)
        self.btn_calcular.clicked.connect(self.generar_preview)
        self.btn_impactar.clicked.connect(self.impactar_db)
        self.btn_exportar.clicked.connect(self.exportar_excel)

        self.radio_masivo.toggled.connect(self.actualizar_combo_filtros)
        self.radio_proveedor.toggled.connect(self.actualizar_combo_filtros)
        self.radio_rubro.toggled.connect(self.actualizar_combo_filtros)
        self.radio_marca.toggled.connect(self.actualizar_combo_filtros)

        # Evento de edición de tabla para recálculo manual
        self.tabla.itemChanged.connect(self.on_celda_editada)
        self._is_updating = False

    def actualizar_combo_filtros(self):
        if self.df is None:
            return

        self.combo_filtro_valor.clear()

        if self.radio_masivo.isChecked():
            self.combo_filtro_valor.setEnabled(False)
            return

        self.combo_filtro_valor.setEnabled(True)

        columna_objetivo = None
        if self.radio_proveedor.isChecked():
            columna_objetivo = self.combo_proveedor.currentText()
        elif self.radio_rubro.isChecked():
            columna_objetivo = self.combo_rubro.currentText()
        elif self.radio_marca.isChecked():
            columna_objetivo = self.combo_marca.currentText()

        if columna_objetivo and columna_objetivo != "-- Seleccionar --":
            valores_unicos = self.df[columna_objetivo].dropna().unique().tolist()
            valores_unicos = [str(v) for v in valores_unicos]
            self.combo_filtro_valor.addItems(sorted(valores_unicos))

    def cargar_archivo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo de precios", "",
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            if file_path.endswith('.csv'):
                self.df = pd.read_csv(file_path)
            else:
                self.df = pd.read_excel(file_path)

            self.lbl_archivo.setText(f"Cargado: {file_path.split('/')[-1]} ({len(self.df)} filas)")

            # Cargar columnas en los combos
            columnas = self.df.columns.tolist()

            for combo in [self.combo_codigo, self.combo_costo, self.combo_proveedor, self.combo_rubro, self.combo_marca]:
                combo.clear()
                combo.addItems(["-- Seleccionar --"] + columnas)

            self.mapeo_group.setEnabled(True)
            self.btn_impactar.setEnabled(False)
            self.btn_exportar.setEnabled(False)
            self.tabla.setRowCount(0)

            # Conectar cambios en combos de mapeo para actualizar las opciones de filtro
            self.combo_proveedor.currentTextChanged.connect(self.actualizar_combo_filtros)
            self.combo_rubro.currentTextChanged.connect(self.actualizar_combo_filtros)
            self.combo_marca.currentTextChanged.connect(self.actualizar_combo_filtros)

        except Exception as e:
            QMessageBox.critical(self, "Error de carga", f"No se pudo cargar el archivo:\n{str(e)}")

    def generar_preview(self):
        if self.df is None:
            return

        col_codigo = self.combo_codigo.currentText()
        col_costo = self.combo_costo.currentText()

        if col_codigo == "-- Seleccionar --" or col_costo == "-- Seleccionar --":
            QMessageBox.warning(self, "Advertencia", "Debe mapear las columnas de Código y Costo Nuevo.")
            return

        # Obtener lógica de filtrado
        df_filtrado = self.df
        if not self.radio_masivo.isChecked():
            valor_filtro = self.combo_filtro_valor.currentText()

            col_filtro = None
            if self.radio_proveedor.isChecked():
                col_filtro = self.combo_proveedor.currentText()
            elif self.radio_rubro.isChecked():
                col_filtro = self.combo_rubro.currentText()
            elif self.radio_marca.isChecked():
                col_filtro = self.combo_marca.currentText()

            if col_filtro == "-- Seleccionar --":
                QMessageBox.warning(self, "Advertencia", f"Debe mapear la columna para el filtro seleccionado.")
                return

            df_filtrado = self.df[self.df[col_filtro].astype(str) == valor_filtro]

        if df_filtrado.empty:
            QMessageBox.information(self, "Sin datos", "No hay filas que coincidan con el filtro.")
            return

        # 1. Traer todos los productos para cruzar (en memoria para no trabar BD)
        self.productos_db = ProductoService.listar_todos()
        db_dict = {p.codigo_barras: p for p in self.productos_db if p.codigo_barras}

        # 2. Iterar DataFrame y cruzar
        margen_global = self.spin_margen.value()

        filas_preview = []
        for index, row in df_filtrado.iterrows():
            cod = str(row.get(col_codigo, "")).strip()
            # Parsear costo nuevo, asumiendo formato numérico.
            try:
                # Intenta limpiar si es string tipo "$ 1.500,50" (basado en memoria de reglas)
                raw_val = str(row.get(col_costo, "0"))
                raw_val = raw_val.replace('$', '').replace(',', '.').strip()
                costo_nuevo = float(raw_val)
            except ValueError:
                costo_nuevo = 0.0

            if cod in db_dict and costo_nuevo > 0:
                prod = db_dict[cod]

                try:
                    pf = ProductoService.calcular_precio_final(costo_nuevo, prod.iva, margen_global)
                except ValueError:
                    pf = 0.0

                filas_preview.append({
                    'id': prod.id,
                    'nombre': prod.nombre,
                    'costo_ant': prod.costo,
                    'costo_nuevo': costo_nuevo,
                    'margen': margen_global,
                    'precio_final': pf,
                    'iva': prod.iva
                })

        if not filas_preview:
            QMessageBox.information(self, "Sin coincidencias", "No se encontraron códigos de barras coincidentes entre el archivo (con los filtros aplicados) y la base de datos.")
            return

        # 3. Llenar QTableWidget
        self._is_updating = True
        self.tabla.setRowCount(len(filas_preview))
        for row_idx, data in enumerate(filas_preview):

            # ID
            item_id = QTableWidgetItem(str(data['id']))
            item_id.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            # Nombre
            item_nom = QTableWidgetItem(data['nombre'])
            item_nom.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            # Costo Ant
            item_ca = QTableWidgetItem(f"{data['costo_ant']:.2f}")
            item_ca.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            # Costo Nuevo (Editable)
            item_cn = QTableWidgetItem(f"{data['costo_nuevo']:.2f}")
            item_cn.setData(Qt.ItemDataRole.UserRole, data['iva']) # Guardar IVA para recalcular

            # Margen (Editable)
            item_m = QTableWidgetItem(f"{data['margen']:.2f}")

            # Precio Final (Solo lectura, se autocalcula si edito cn o m)
            item_pf = QTableWidgetItem(f"{data['precio_final']:.2f}")
            item_pf.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            self.tabla.setItem(row_idx, 0, item_id)
            self.tabla.setItem(row_idx, 1, item_nom)
            self.tabla.setItem(row_idx, 2, item_ca)
            self.tabla.setItem(row_idx, 3, item_cn)
            self.tabla.setItem(row_idx, 4, item_m)
            self.tabla.setItem(row_idx, 5, item_pf)

        self._is_updating = False

        self.btn_impactar.setEnabled(True)
        self.btn_exportar.setEnabled(True)
        QMessageBox.information(self, "Cálculo Exitoso", f"Se previsualizan {len(filas_preview)} productos listos para actualizar.")

    def on_celda_editada(self, item):
        if self._is_updating:
            return

        col = item.column()
        row = item.row()

        # Si edita Costo Nuevo (3) o Margen (4)
        if col in (3, 4):
            try:
                self._is_updating = True

                # Obtener valores actuales
                item_cn = self.tabla.item(row, 3)
                item_m = self.tabla.item(row, 4)
                item_pf = self.tabla.item(row, 5)

                cn_val = float(item_cn.text().replace(',', '.'))
                m_val = float(item_m.text().replace(',', '.'))
                iva = item_cn.data(Qt.ItemDataRole.UserRole)

                # Recalcular (usando el servicio para mantener consistencia financiera)
                pf_nuevo = ProductoService.calcular_precio_final(cn_val, iva, m_val)
                item_pf.setText(f"{pf_nuevo:.2f}")

            except ValueError:
                pass # Ignorar si tipearon texto no numérico momentáneamente
            finally:
                self._is_updating = False

    def impactar_db(self):
        reply = QMessageBox.question(
            self, "Confirmar Actualización",
            f"¿Está seguro de impactar los cambios de {self.tabla.rowCount()} productos en la base de datos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            actualizaciones = []
            for row in range(self.tabla.rowCount()):
                try:
                    pid = int(self.tabla.item(row, 0).text())
                    c_nuevo = float(self.tabla.item(row, 3).text().replace(',', '.'))
                    pf_nuevo = float(self.tabla.item(row, 5).text().replace(',', '.'))

                    actualizaciones.append({
                        'id': pid,
                        'costo': c_nuevo,
                        'precio_minorista': pf_nuevo
                    })
                except Exception:
                    continue

            try:
                afectados = ProductoService.actualizar_precios_masivo(actualizaciones)
                QMessageBox.information(self, "Éxito", f"Se actualizaron {afectados} productos correctamente.")
                # Limpiar tras éxito
                self.tabla.setRowCount(0)
                self.btn_impactar.setEnabled(False)
                self.btn_exportar.setEnabled(False)
            except Exception as e:
                QMessageBox.critical(self, "Error en BD", f"Ocurrió un error al guardar:\n{str(e)}")

    def exportar_excel(self):
        if self.tabla.rowCount() == 0:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Excel", "Lista_Precios_Actualizada.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            data = []
            for row in range(self.tabla.rowCount()):
                data.append({
                    "ID": int(self.tabla.item(row, 0).text()),
                    "Nombre": self.tabla.item(row, 1).text(),
                    "Costo Anterior": float(self.tabla.item(row, 2).text().replace(',', '.')),
                    "Costo Nuevo": float(self.tabla.item(row, 3).text().replace(',', '.')),
                    "Margen %": float(self.tabla.item(row, 4).text().replace(',', '.')),
                    "Precio Final": float(self.tabla.item(row, 5).text().replace(',', '.'))
                })

            df_export = pd.DataFrame(data)
            df_export.to_excel(file_path, index=False)
            QMessageBox.information(self, "Éxito", "Archivo exportado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error al Exportar", f"No se pudo guardar el archivo:\n{str(e)}")
