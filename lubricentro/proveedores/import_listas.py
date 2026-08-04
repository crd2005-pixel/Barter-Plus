# -*- coding: utf-8 -*-
"""
proveedores/import_listas.py
UI simplificada para importar el Inventario Maestro Unificado mediante UPSERT estricto.
"""

import os
from datetime import datetime
import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox, QProgressBar, QTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# DB principal
import sys; import os; sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); from db import SessionLocal
from db.models.productos import Producto, Marca
from db.models.proveedores import Proveedor
from sqlalchemy.exc import IntegrityError

class ImportWorker(QThread):
    progress = pyqtSignal(int)
    log_msg = pyqtSignal(str)
    finished_import = pyqtSignal(int, int) # actualizados, nuevos
    error = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            self.log_msg.emit(f"Leyendo archivo: {self.file_path}")
            df = pd.read_excel(self.file_path)

            # Verificar columnas requeridas
            required_cols = [
                'sku_interno', 'proveedor', 'codigo_proveedor',
                'marca', 'descripcion', 'costo_neto',
                'contenido_caja', 'fecha_actualizacion'
            ]
            missing_cols = [c for c in required_cols if c not in df.columns]
            if missing_cols:
                self.error.emit(f"Faltan columnas obligatorias: {', '.join(missing_cols)}")
                return

            total_rows = len(df)
            self.log_msg.emit(f"Se encontraron {total_rows} filas para procesar.")

            actualizados = 0
            nuevos = 0

            with SessionLocal() as session:
                try:
                    for index, row in df.iterrows():
                        sku_interno = str(row['sku_interno']).strip()
                        if not sku_interno or pd.isna(row['sku_interno']):
                            continue

                        proveedor_nombre = str(row['proveedor']).strip() if pd.notna(row['proveedor']) else ''
                        codigo_proveedor = str(row['codigo_proveedor']).strip() if pd.notna(row['codigo_proveedor']) else ''
                        marca_nombre = str(row['marca']).strip() if pd.notna(row['marca']) else ''
                        descripcion = str(row['descripcion']).strip() if pd.notna(row['descripcion']) else ''

                        try:
                            costo_neto = float(row['costo_neto'])
                        except (ValueError, TypeError):
                            costo_neto = 0.0

                        try:
                            contenido_caja = float(row['contenido_caja'])
                        except (ValueError, TypeError):
                            contenido_caja = 1.0

                        # Resolución de IDs: Proveedor
                        proveedor = None
                        if proveedor_nombre:
                            proveedor = session.query(Proveedor).filter_by(nombre=proveedor_nombre).first()
                            if not proveedor:
                                proveedor = Proveedor(nombre=proveedor_nombre)
                                session.add(proveedor)
                                session.flush() # Obtener ID generado

                        # Resolución de IDs: Marca
                        marca = None
                        if marca_nombre:
                            marca = session.query(Marca).filter_by(nombre=marca_nombre).first()
                            if not marca:
                                marca = Marca(nombre=marca_nombre)
                                session.add(marca)
                                session.flush() # Obtener ID generado

                        # Buscar producto por sku_interno
                        producto = session.query(Producto).filter_by(sku=sku_interno).first()

                        if producto:
                            # UPSERT: Update
                            producto.costo = costo_neto
                            if proveedor:
                                producto.proveedor_id = proveedor.id
                            producto.actualizado_en = datetime.utcnow()
                            actualizados += 1
                        else:
                            # UPSERT: Insert
                            nuevo_producto = Producto(
                                sku=sku_interno,
                                nombre=descripcion,
                                costo=costo_neto,
                                codigo_proveedor=codigo_proveedor,
                                presentacion_cantidad=contenido_caja
                            )
                            if proveedor:
                                nuevo_producto.proveedor_id = proveedor.id
                            if marca:
                                nuevo_producto.marca_id = marca.id

                            session.add(nuevo_producto)
                            nuevos += 1

                        # Progreso
                        if index % 10 == 0 or index == total_rows - 1:
                            self.progress.emit(int(((index + 1) / total_rows) * 100))

                    session.commit()
                except Exception as e:
                    session.rollback()
                    raise e

            self.finished_import.emit(actualizados, nuevos)

        except Exception as e:
            self.error.emit(f"Error inesperado: {str(e)}")


class ImportadorListasTab(QWidget):
    def __init__(self, on_after_import=None, parent=None):
        super().__init__(parent)
        self._on_after_import = on_after_import
        self.worker = None
        self._ui()
        self._bind()

    def _ui(self):
        lay = QVBoxLayout(self)

        top_lay = QHBoxLayout()
        self.btn_import = QPushButton("Cargar Inventario Maestro Unificado")
        self.btn_import.setMinimumHeight(50)
        top_lay.addStretch(1)
        top_lay.addWidget(self.btn_import, 2)
        top_lay.addStretch(1)
        lay.addLayout(top_lay)

        lay.addSpacing(20)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        lay.addWidget(self.progress_bar)

        lay.addSpacing(20)

        lay.addWidget(QLabel("Log de Resultados:"))
        self.txt_log = QTextEdit(self)
        self.txt_log.setReadOnly(True)
        lay.addWidget(self.txt_log)

        self.setLayout(lay)

    def _bind(self):
        self.btn_import.clicked.connect(self._importar_excel)

    def _log(self, text):
        self.txt_log.append(text)

    def _importar_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Inventario Maestro Unificado",
            "",
            "Excel (*.xlsx)"
        )
        if not path:
            return

        self.txt_log.clear()
        self.progress_bar.setValue(0)
        self.btn_import.setEnabled(False)
        self._log(f"Iniciando importación: {os.path.basename(path)}")

        self.worker = ImportWorker(path)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.log_msg.connect(self._log)
        self.worker.error.connect(self._on_error)
        self.worker.finished_import.connect(self._on_finished)
        self.worker.start()

    def _on_error(self, msg):
        self._log(f"<span style='color:red'><b>ERROR:</b> {msg}</span>")
        QMessageBox.critical(self, "Error", msg)
        self.btn_import.setEnabled(True)

    def _on_finished(self, actualizados, nuevos):
        self.progress_bar.setValue(100)
        self._log(f"<span style='color:green'><b>¡Importación completada!</b></span>")
        self._log(f"Productos actualizados: {actualizados}")
        self._log(f"Productos nuevos (insertados): {nuevos}")

        QMessageBox.information(
            self,
            "Importación completada",
            f"Proceso finalizado con éxito.\n\nActualizados: {actualizados}\nNuevos: {nuevos}"
        )
        self.btn_import.setEnabled(True)

        if self._on_after_import:
            self._on_after_import()
