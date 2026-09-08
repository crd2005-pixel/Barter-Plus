import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QComboBox, QRadioButton,
    QDoubleSpinBox, QMessageBox, QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt
from services.producto_service import ProductoService

class PreciosTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.productos_db = []

        # --- ZONA DE FILTROS ---
        self.aumentos_group = QGroupBox("Gestor de Precios Interno")
        self.aumentos_layout = QFormLayout()

        self.tipo_aumento_layout = QHBoxLayout()
        self.radio_masivo = QRadioButton("Masivo")
        self.radio_masivo.setChecked(True)
        self.radio_rubro = QRadioButton("Por Categoria/Rubro")
        self.radio_marca = QRadioButton("Por Marca")

        self.tipo_aumento_layout.addWidget(self.radio_masivo)
        self.tipo_aumento_layout.addWidget(self.radio_rubro)
        self.tipo_aumento_layout.addWidget(self.radio_marca)
        self.tipo_aumento_layout.addStretch()

        # Valor a filtrar
        self.filtro_valor_layout = QHBoxLayout()
        self.combo_filtro_valor = QComboBox()
        self.combo_filtro_valor.setEnabled(False)
        self.filtro_valor_layout.addWidget(QLabel("Seleccionar:"))
        self.filtro_valor_layout.addWidget(self.combo_filtro_valor)
        self.filtro_valor_layout.addStretch()

        self.spin_margen = QDoubleSpinBox()
        self.spin_margen.setRange(0, 99.99)
        self.spin_margen.setValue(30.0)

        self.btn_cargar_datos = QPushButton("Cargar Datos de BD y Calcular")

        self.aumentos_layout.addRow("Filtro de Aplicación:", self.tipo_aumento_layout)
        self.aumentos_layout.addRow("Valor:", self.filtro_valor_layout)
        self.aumentos_layout.addRow("Margen General a Aplicar (%):", self.spin_margen)
        self.aumentos_layout.addRow("", self.btn_cargar_datos)

        self.aumentos_group.setLayout(self.aumentos_layout)
        self.layout.addWidget(self.aumentos_group)

        # --- ZONA DE PREVISUALIZACIÓN ---
        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels([
            "ID BD", "SKU Interno", "Nombre", "Costo Base (PM)", "Costo Nuevo (M. Edit)", "Margen %", "Precio Final"
        ])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.setAlternatingRowColors(True)
        self.layout.addWidget(self.tabla)

        # --- ACCIONES FINALES ---
        self.acciones_layout = QHBoxLayout()
        self.btn_impactar = QPushButton("Guardar Precios en Base de Datos")
        self.btn_impactar.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.btn_impactar.setEnabled(False)

        self.acciones_layout.addStretch()
        self.acciones_layout.addWidget(self.btn_impactar)
        self.layout.addLayout(self.acciones_layout)

        # --- CONEXIONES ---
        self.radio_masivo.toggled.connect(self.actualizar_combo_filtros)
        self.radio_rubro.toggled.connect(self.actualizar_combo_filtros)
        self.radio_marca.toggled.connect(self.actualizar_combo_filtros)

        self.btn_cargar_datos.clicked.connect(self.cargar_y_calcular)
        self.btn_impactar.clicked.connect(self.impactar_db)

        self.tabla.itemChanged.connect(self.on_celda_editada)
        self._is_updating = False

    def actualizar_combo_filtros(self):
        self.combo_filtro_valor.clear()

        if self.radio_masivo.isChecked():
            self.combo_filtro_valor.setEnabled(False)
            return

        self.combo_filtro_valor.setEnabled(True)

        # Traer valores únicos desde la BD para filtrar
        self.productos_db = ProductoService.listar_todos()
        valores_unicos = set()

        if self.radio_rubro.isChecked():
            for p in self.productos_db:
                if p.categoria and p.categoria.nombre:
                    valores_unicos.add(p.categoria.nombre)
                elif p.rubro: # Fallback al string si se usa
                    valores_unicos.add(p.rubro)
        elif self.radio_marca.isChecked():
            for p in self.productos_db:
                if p.marca and p.marca.nombre:
                    valores_unicos.add(p.marca.nombre)

        self.combo_filtro_valor.addItems(sorted(list(valores_unicos)))

    def cargar_y_calcular(self):
        self.productos_db = ProductoService.listar_todos()
        margen_global = self.spin_margen.value()

        filas_preview = []
        for prod in self.productos_db:
            # Aplicar filtro si no es masivo
            if self.radio_rubro.isChecked():
                cat_nombre = prod.categoria.nombre if prod.categoria else prod.rubro
                if cat_nombre != self.combo_filtro_valor.currentText():
                    continue
            elif self.radio_marca.isChecked():
                marca_nombre = prod.marca.nombre if prod.marca else ""
                if marca_nombre != self.combo_filtro_valor.currentText():
                    continue

            try:
                # Calculamos usando el costo actual que tiene la BD (que debió ser actualizado por proveedores_view)
                pf = ProductoService.calcular_precio_final(prod.costo, prod.iva, margen_global)
            except ValueError:
                pf = 0.0

            filas_preview.append({
                'id': prod.id,
                'sku': prod.sku or "",
                'nombre': prod.nombre,
                'costo_ant': prod.costo,
                'costo_nuevo': prod.costo, # Inicialmente es el mismo, el usuario puede ajustarlo manual aquí
                'margen': margen_global,
                'precio_final': pf,
                'iva': prod.iva
            })

        if not filas_preview:
            QMessageBox.information(self, "Sin datos", "No hay productos para mostrar con este filtro.")
            self.tabla.setRowCount(0)
            self.btn_impactar.setEnabled(False)
            return

        self._is_updating = True
        self.tabla.setRowCount(len(filas_preview))
        for row_idx, data in enumerate(filas_preview):
            item_id = QTableWidgetItem(str(data['id']))
            item_id.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            item_sku = QTableWidgetItem(data['sku'])
            item_sku.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            item_nom = QTableWidgetItem(data['nombre'])
            item_nom.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            item_ca = QTableWidgetItem(f"{data['costo_ant']:.2f}")
            item_ca.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            item_cn = QTableWidgetItem(f"{data['costo_nuevo']:.2f}")
            item_cn.setData(Qt.ItemDataRole.UserRole, data['iva'])

            item_m = QTableWidgetItem(f"{data['margen']:.2f}")

            item_pf = QTableWidgetItem(f"{data['precio_final']:.2f}")
            item_pf.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            self.tabla.setItem(row_idx, 0, item_id)
            self.tabla.setItem(row_idx, 1, item_sku)
            self.tabla.setItem(row_idx, 2, item_nom)
            self.tabla.setItem(row_idx, 3, item_ca)
            self.tabla.setItem(row_idx, 4, item_cn)
            self.tabla.setItem(row_idx, 5, item_m)
            self.tabla.setItem(row_idx, 6, item_pf)

        self._is_updating = False
        self.btn_impactar.setEnabled(True)

    def on_celda_editada(self, item):
        if self._is_updating:
            return

        col = item.column()
        row = item.row()

        # Edición manual de costo nuevo o margen
        if col in (4, 5):
            try:
                self._is_updating = True
                item_cn = self.tabla.item(row, 4)
                item_m = self.tabla.item(row, 5)
                item_pf = self.tabla.item(row, 6)

                cn_val = float(item_cn.text().replace(',', '.'))
                m_val = float(item_m.text().replace(',', '.'))
                iva = item_cn.data(Qt.ItemDataRole.UserRole)

                pf_nuevo = ProductoService.calcular_precio_final(cn_val, iva, m_val)
                item_pf.setText(f"{pf_nuevo:.2f}")
            except ValueError:
                pass
            finally:
                self._is_updating = False

    def impactar_db(self):
        reply = QMessageBox.question(
            self, "Confirmar",
            "¿Guardar los precios finales en la base de datos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            actualizaciones = []
            for row in range(self.tabla.rowCount()):
                try:
                    pid = int(self.tabla.item(row, 0).text())
                    c_nuevo = float(self.tabla.item(row, 4).text().replace(',', '.'))
                    pf_nuevo = float(self.tabla.item(row, 6).text().replace(',', '.'))

                    actualizaciones.append({
                        'id': pid,
                        'costo': c_nuevo,
                        'precio_minorista': pf_nuevo
                    })
                except Exception:
                    continue

            try:
                afectados = ProductoService.actualizar_precios_masivo(actualizaciones)
                QMessageBox.information(self, "Éxito", f"Se actualizaron {afectados} productos.")
                self.tabla.setRowCount(0)
                self.btn_impactar.setEnabled(False)
            except Exception as e:
                QMessageBox.critical(self, "Error en BD", f"Error:\n{str(e)}")
