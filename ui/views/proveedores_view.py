import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox,
    QLabel, QComboBox, QFormLayout, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from services.proveedor_import_service import ProveedorImportService
from services.producto_service import ProductoService
from ui.components.pagination import PaginationWidget

class ProveedoresTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.df = None
        self.filas_preview = []

        # --- ZONA DE IMPORTACIÓN MAESTRA ---
        self.import_group = QGroupBox("Importar Lista Maestra de Proveedores")
        self.import_layout = QVBoxLayout()

        # Selección de archivo
        self.box_archivo = QHBoxLayout()
        self.btn_cargar = QPushButton("Cargar Excel / CSV")
        self.lbl_archivo = QLabel("Ningún archivo seleccionado")

        self.box_archivo.addWidget(self.btn_cargar)
        self.box_archivo.addWidget(self.lbl_archivo)
        self.box_archivo.addStretch()
        self.import_layout.addLayout(self.box_archivo)

        # Mapeo de columnas
        self.form_mapeo = QFormLayout()

        self.map_sku = QComboBox()
        self.map_proveedor = QComboBox()
        self.map_marca = QComboBox()
        self.map_desc = QComboBox()
        self.map_costo = QComboBox()

        self.form_mapeo.addRow("SKU Interno (Obligatorio)*:", self.map_sku)
        self.form_mapeo.addRow("Proveedor:", self.map_proveedor)
        self.form_mapeo.addRow("Marca:", self.map_marca)
        self.form_mapeo.addRow("Nombre/Descripción:", self.map_desc)
        self.form_mapeo.addRow("Costo Neto Base*:", self.map_costo)

        self.import_layout.addLayout(self.form_mapeo)

        # Acciones de Previsualización
        self.box_acciones_prev = QHBoxLayout()
        self.btn_previsualizar = QPushButton("Generar Previsualización")
        self.btn_previsualizar.setEnabled(False)
        self.box_acciones_prev.addStretch()
        self.box_acciones_prev.addWidget(self.btn_previsualizar)
        self.import_layout.addLayout(self.box_acciones_prev)

        self.import_group.setLayout(self.import_layout)
        self.layout.addWidget(self.import_group)

        # --- ZONA DE PREVISUALIZACIÓN Y APROBACIÓN ---
        self.preview_group = QGroupBox("Previsualización de Cambios (Por Impactar)")
        self.preview_layout = QVBoxLayout()

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels([
            "SKU Interno", "Nombre", "Proveedor", "Costo Anterior", "Costo Nuevo"
        ])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_layout.addWidget(self.tabla)

        self.paginacion = PaginationWidget(limit=50)
        self.paginacion.page_changed.connect(self.render_tabla_pagina)
        self.preview_layout.addWidget(self.paginacion)

        self.box_acciones_finales = QHBoxLayout()
        self.btn_aprobar = QPushButton("Aprobar y Cargar BD")
        self.btn_aprobar.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 10px;")
        self.btn_aprobar.setEnabled(False)
        self.box_acciones_finales.addStretch()
        self.box_acciones_finales.addWidget(self.btn_aprobar)
        self.preview_layout.addLayout(self.box_acciones_finales)

        self.preview_group.setLayout(self.preview_layout)
        self.layout.addWidget(self.preview_group)

        # Conexiones
        self.btn_cargar.clicked.connect(self.cargar_archivo)
        self.btn_previsualizar.clicked.connect(self.generar_previsualizacion)
        self.btn_aprobar.clicked.connect(self.impactar_datos)

    def cargar_archivo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Lista de Proveedor", "",
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

            columnas = self.df.columns.tolist()

            for combo in [self.map_sku, self.map_proveedor, self.map_marca, self.map_desc, self.map_costo]:
                combo.clear()
                combo.addItems(["-- Ignorar/Seleccionar --"] + columnas)

            self.btn_previsualizar.setEnabled(True)
            self.btn_aprobar.setEnabled(False)
            self.filas_preview = []
            self.paginacion.set_total_items(0)

        except Exception as e:
            QMessageBox.critical(self, "Error de carga", f"No se pudo cargar el archivo:\n{str(e)}")

    def generar_previsualizacion(self):
        if self.df is None:
            return

        col_sku = self.map_sku.currentText()
        col_costo = self.map_costo.currentText()

        if col_sku == "-- Ignorar/Seleccionar --" or col_costo == "-- Ignorar/Seleccionar --":
            QMessageBox.warning(self, "Advertencia", "Debe mapear obligatoriamente el 'SKU Interno' y el 'Costo Neto Base'.")
            return

        # Traer caché de BD para comparar costos anteriores
        productos_db = ProductoService.listar_todos()
        cache_db = {p.sku.lower(): p for p in productos_db if p.sku}

        df_limpio = self.df.fillna("")
        self.filas_preview = []

        for index, row in df_limpio.iterrows():
            sku_val = str(row.get(col_sku, "")).strip()
            if not sku_val:
                continue

            try:
                raw_costo = str(row.get(col_costo, "0"))
                raw_costo = raw_costo.replace('$', '').replace(',', '.').strip()
                costo_val = float(raw_costo)
            except ValueError:
                costo_val = 0.0

            fila_data = {
                'sku': sku_val,
                'costo': costo_val,
                'proveedor': "",
                'marca': "",
                'nombre': ""
            }

            if self.map_proveedor.currentText() != "-- Ignorar/Seleccionar --":
                fila_data['proveedor'] = str(row.get(self.map_proveedor.currentText(), "")).strip()

            if self.map_marca.currentText() != "-- Ignorar/Seleccionar --":
                fila_data['marca'] = str(row.get(self.map_marca.currentText(), "")).strip()

            if self.map_desc.currentText() != "-- Ignorar/Seleccionar --":
                fila_data['nombre'] = str(row.get(self.map_desc.currentText(), "")).strip()

            # Buscar costo anterior
            sku_key = sku_val.lower()
            if sku_key in cache_db:
                fila_data['costo_ant'] = cache_db[sku_key].costo
                if not fila_data['nombre']:
                    fila_data['nombre'] = cache_db[sku_key].nombre
                if not fila_data['proveedor'] and cache_db[sku_key].proveedor:
                    fila_data['proveedor'] = cache_db[sku_key].proveedor.nombre
            else:
                fila_data['costo_ant'] = 0.0 # Es nuevo

            self.filas_preview.append(fila_data)

        self.paginacion.set_total_items(len(self.filas_preview))
        if len(self.filas_preview) > 0:
            self.btn_aprobar.setEnabled(True)
            QMessageBox.information(self, "Previsualización", f"Se previsualizarán {len(self.filas_preview)} filas de la lista maestra.")

    def render_tabla_pagina(self, page_index):
        sl = self.paginacion.get_slice()
        datos_pagina = self.filas_preview[sl]

        self.tabla.setRowCount(len(datos_pagina))

        color_nuevo = QBrush(QColor(41, 128, 185, 50)) # Azul sutil para nuevos
        color_cambio = QBrush(QColor(243, 156, 18, 50)) # Naranja sutil para cambios

        for r, data in enumerate(datos_pagina):
            item_sku = QTableWidgetItem(data['sku'])
            item_nom = QTableWidgetItem(data['nombre'])
            item_prov = QTableWidgetItem(data['proveedor'])

            c_ant = data.get('costo_ant', 0.0)
            c_nue = data['costo']

            item_ca = QTableWidgetItem(f"$ {c_ant:.2f}" if c_ant > 0 else "NUEVO")
            item_cn = QTableWidgetItem(f"$ {c_nue:.2f}")

            if c_ant == 0.0:
                item_sku.setBackground(color_nuevo)
                item_nom.setBackground(color_nuevo)
                item_ca.setBackground(color_nuevo)
                item_cn.setBackground(color_nuevo)
            elif abs(c_ant - c_nue) > 0.01:
                item_cn.setBackground(color_cambio)

            self.tabla.setItem(r, 0, item_sku)
            self.tabla.setItem(r, 1, item_nom)
            self.tabla.setItem(r, 2, item_prov)
            self.tabla.setItem(r, 3, item_ca)
            self.tabla.setItem(r, 4, item_cn)

    def impactar_datos(self):
        if not self.filas_preview:
            return

        reply = QMessageBox.question(
            self, "Confirmar UPSERT",
            f"Se van a impactar {len(self.filas_preview)} filas en la Base de Datos.\n¿Desea continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                nuevos, actualizados, errores = ProveedorImportService.procesar_importacion_maestra(self.filas_preview)
                msg = f"Importación Completada.\n\nNuevos creados: {nuevos}\nActualizados: {actualizados}\nErrores omitidos: {errores}"
                QMessageBox.information(self, "Resultado", msg)

                # Resetear UI
                self.df = None
                self.filas_preview = []
                self.lbl_archivo.setText("Ningún archivo seleccionado")
                self.btn_previsualizar.setEnabled(False)
                self.btn_aprobar.setEnabled(False)
                self.paginacion.set_total_items(0)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Fallo al actualizar la base de datos:\n{str(e)}")
