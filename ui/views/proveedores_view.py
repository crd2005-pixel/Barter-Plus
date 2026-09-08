import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox,
    QLabel, QComboBox, QFormLayout, QGroupBox
)
from PyQt6.QtCore import Qt
from services.proveedor_import_service import ProveedorImportService

class ProveedoresTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.df = None

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

        # Acciones
        self.box_acciones = QHBoxLayout()
        self.btn_procesar = QPushButton("Procesar y Actualizar BD")
        self.btn_procesar.setStyleSheet("background-color: #2e7d32; color: white;")
        self.btn_procesar.setEnabled(False)

        self.box_acciones.addStretch()
        self.box_acciones.addWidget(self.btn_procesar)
        self.import_layout.addLayout(self.box_acciones)

        self.import_group.setLayout(self.import_layout)
        self.layout.addWidget(self.import_group)
        self.layout.addStretch()

        # Conexiones
        self.btn_cargar.clicked.connect(self.cargar_archivo)
        self.btn_procesar.clicked.connect(self.procesar_datos)

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

            self.btn_procesar.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Error de carga", f"No se pudo cargar el archivo:\n{str(e)}")

    def procesar_datos(self):
        if self.df is None:
            return

        col_sku = self.map_sku.currentText()
        col_costo = self.map_costo.currentText()

        if col_sku == "-- Ignorar/Seleccionar --" or col_costo == "-- Ignorar/Seleccionar --":
            QMessageBox.warning(self, "Advertencia", "Debe mapear obligatoriamente el 'SKU Interno' y el 'Costo Neto Base'.")
            return

        # Sanitizar DataFrame para evitar que celdas vacías sean procesadas como el string "nan"
        df_limpio = self.df.fillna("")

        # Armar la lista de diccionarios
        filas = []
        for index, row in df_limpio.iterrows():
            # Extraer y limpiar
            try:
                # Limpieza básica de costo
                raw_costo = str(row.get(col_costo, "0"))
                raw_costo = raw_costo.replace('$', '').replace(',', '.').strip()
                costo_val = float(raw_costo)
            except ValueError:
                costo_val = 0.0

            fila_data = {
                'sku': str(row.get(col_sku, "")).strip(),
                'costo': costo_val
            }

            if self.map_proveedor.currentText() != "-- Ignorar/Seleccionar --":
                fila_data['proveedor'] = str(row.get(self.map_proveedor.currentText(), "")).strip()

            if self.map_marca.currentText() != "-- Ignorar/Seleccionar --":
                fila_data['marca'] = str(row.get(self.map_marca.currentText(), "")).strip()

            if self.map_desc.currentText() != "-- Ignorar/Seleccionar --":
                fila_data['nombre'] = str(row.get(self.map_desc.currentText(), "")).strip()

            filas.append(fila_data)

        # Confirmar y Enviar al Service
        reply = QMessageBox.question(
            self, "Confirmar UPSERT",
            f"Se van a procesar {len(filas)} filas. Esto actualizará costos y creará productos faltantes.\n¿Desea continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                nuevos, actualizados, errores = ProveedorImportService.procesar_importacion_maestra(filas)
                msg = f"Importación Completada.\n\nNuevos creados: {nuevos}\nActualizados: {actualizados}\nErrores omitidos: {errores}"
                QMessageBox.information(self, "Resultado", msg)

                # Resetear UI
                self.df = None
                self.lbl_archivo.setText("Ningún archivo seleccionado")
                self.btn_procesar.setEnabled(False)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Fallo al actualizar la base de datos:\n{str(e)}")
