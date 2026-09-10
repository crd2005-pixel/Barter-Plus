from ui.components.pagination import PaginationWidget
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog, QDialog,
    QFormLayout, QLineEdit, QComboBox, QTabWidget, QSpinBox, QDateEdit, QCompleter, QDoubleSpinBox, QFileDialog, QGroupBox, QSplitter
)
from PyQt6.QtCore import Qt, QDate, QStringListModel
from PyQt6.QtGui import QFont, QBrush, QColor
from services.compras_service import ComprasService
from services.proveedor_service import ProveedorService
from services.producto_service import ProductoService
import datetime as dt

class SugerenciasTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.cargar_datos()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Botonera
        btn_lay = QHBoxLayout()
        self.btn_recargar = QPushButton("Recargar Sugerencias")
        self.btn_recargar.clicked.connect(self.cargar_datos)

        self.btn_exportar = QPushButton("Exportar Pedido (Texto/Clipboard)")
        self.btn_exportar.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.btn_exportar.clicked.connect(self.exportar_pedido)

        btn_lay.addWidget(self.btn_recargar)
        btn_lay.addStretch()
        btn_lay.addWidget(self.btn_exportar)
        layout.addLayout(btn_lay)

        # Grilla
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["SKU", "Proveedor", "Producto", "Stock Actual", "Stock Mínimo", "Cant. Sugerida"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.table)

    def cargar_datos(self):
        sugerencias = ComprasService.obtener_sugerencias_pedido()
        self.table.setRowCount(len(sugerencias))

        for row, s in enumerate(sugerencias):
            p = s['producto']
            cant = s['cantidad_sugerida']

            prov_nom = p.proveedor.nombre if p.proveedor else "Sin Proveedor"

            self.table.setItem(row, 0, QTableWidgetItem(p.sku or "-"))
            self.table.setItem(row, 1, QTableWidgetItem(prov_nom))
            self.table.setItem(row, 2, QTableWidgetItem(p.nombre))

            i_act = QTableWidgetItem(str(p.stock_actual))
            if p.stock_actual <= 0:
                i_act.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 3, i_act)

            self.table.setItem(row, 4, QTableWidgetItem(str(p.stock_minimo)))

            i_sug = QTableWidgetItem(str(cant))
            font = QFont()
            font.setBold(True)
            i_sug.setFont(font)
            self.table.setItem(row, 5, i_sug)

    def exportar_pedido(self):
        from PyQt6.QtWidgets import QApplication
        filas = self.table.rowCount()
        if filas == 0:
            QMessageBox.warning(self, "Vacio", "No hay sugerencias para exportar.")
            return

        lineas = ["--- PEDIDO SUGERIDO ---"]
        for r in range(filas):
            prov = self.table.item(r, 1).text()
            prod = self.table.item(r, 2).text()
            cant = self.table.item(r, 5).text()
            lineas.append(f"[{prov}] {prod} -> Pedir: {cant}")

        texto_final = "\n".join(lineas)
        clipboard = QApplication.clipboard()
        clipboard.setText(texto_final)

        QMessageBox.information(self, "Exportado", "El pedido ha sido copiado al portapapeles. Puede pegarlo en WhatsApp o Email.")


class IngresoFacturaTab(QWidget):
    def __init__(self):
        super().__init__()
        self.carrito = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Cabecera de Factura
        header_form = QFormLayout()

        self.combo_proveedor = QComboBox()
        self.combo_proveedor.setEditable(True)
        self.combo_proveedor.setPlaceholderText("Seleccionar Proveedor...")
        self.completer_prov = QCompleter()
        self.completer_prov.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer_prov.setFilterMode(Qt.MatchFlag.MatchContains)
        self.combo_proveedor.setCompleter(self.completer_prov)

        self.txt_factura = QLineEdit()
        self.txt_factura.setPlaceholderText("0001-00000001")

        self.date_factura = QDateEdit()
        self.date_factura.setCalendarPopup(True)
        self.date_factura.setDate(QDate.currentDate())

        header_form.addRow("Proveedor:", self.combo_proveedor)
        header_form.addRow("Nº Factura:", self.txt_factura)
        header_form.addRow("Fecha:", self.date_factura)

        layout.addLayout(header_form)

        # Buscador de Productos
        buscar_lay = QHBoxLayout()
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Ingresar Nombre, SKU o Cód. Barras...")

        self.completer_prod = QCompleter()
        self.completer_prod.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer_prod.setFilterMode(Qt.MatchFlag.MatchContains)
        self.txt_buscar.setCompleter(self.completer_prod)

        self.spin_cant = QDoubleSpinBox()
        self.spin_cant.setRange(0.01, 99999.0)
        self.spin_cant.setValue(1.0)

        self.btn_agregar = QPushButton("Agregar al Ingreso")
        self.btn_agregar.clicked.connect(self.agregar_item)

        buscar_lay.addWidget(QLabel("Producto:"))
        buscar_lay.addWidget(self.txt_buscar)
        buscar_lay.addWidget(QLabel("Cant:"))
        buscar_lay.addWidget(self.spin_cant)
        buscar_lay.addWidget(self.btn_agregar)

        layout.addLayout(buscar_lay)

        # Grilla editable
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Producto", "Cant. Comprada", "Nuevo Costo Unitario", "Subtotal"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.table.itemChanged.connect(self.recalcular_totales)

        # Panel inferior
        bot_lay = QHBoxLayout()
        self.lbl_total = QLabel("Total Factura: $0.00")
        self.lbl_total.setStyleSheet("font-size: 20px; font-weight: bold;")

        self.btn_guardar = QPushButton("Guardar Ingreso de Stock")
        self.btn_guardar.setStyleSheet("background-color: #0275d8; color: white; font-weight: bold; padding: 10px;")
        self.btn_guardar.clicked.connect(self.procesar_compra)

        bot_lay.addStretch()
        bot_lay.addWidget(self.lbl_total)
        bot_lay.addWidget(self.btn_guardar)

        layout.addLayout(bot_lay)

        self.cargar_datos_base()

    def cargar_datos_base(self):
        # Cargar Proveedores
        from database.conexion import get_session
        from database.models.proveedor import Proveedor
        from sqlalchemy import select
        with get_session() as session:
            provs = session.scalars(select(Proveedor)).all()
            self.combo_proveedor.clear()
            nombres_p = []
            for p in provs:
                self.combo_proveedor.addItem(p.nombre, p.id)
                nombres_p.append(p.nombre)
            self.completer_prov.setModel(QStringListModel(nombres_p))

        # Cargar completador de productos
        prods = ProductoService.listar_nombres()
        self.completer_prod.setModel(QStringListModel(prods))

    def agregar_item(self):
        query = self.txt_buscar.text().strip()
        if not query: return

        prod = ProductoService.buscar_por_query_flexible(query)
        if not prod:
            QMessageBox.warning(self, "No encontrado", "Producto no encontrado.")
            return

        cant = self.spin_cant.value()

        # Check if exists in cart
        for item in self.carrito:
            if item['id'] == prod.id:
                item['cantidad'] += cant
                self.render_carrito()
                self.txt_buscar.clear()
                self.spin_cant.setValue(1.0)
                return

        self.carrito.append({
            'id': prod.id,
            'nombre': prod.nombre,
            'cantidad': cant,
            'costo': prod.costo
        })
        self.render_carrito()
        self.txt_buscar.clear()
        self.spin_cant.setValue(1.0)

    def render_carrito(self):
        self.table.itemChanged.disconnect(self.recalcular_totales)
        self.table.setRowCount(len(self.carrito))

        total = 0.0
        for r, item in enumerate(self.carrito):
            i_id = QTableWidgetItem(str(item['id']))
            i_id.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            i_nom = QTableWidgetItem(item['nombre'])
            i_nom.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            i_can = QTableWidgetItem(str(item['cantidad']))
            i_cos = QTableWidgetItem(str(item['costo']))

            sub = item['cantidad'] * item['costo']
            total += sub
            i_sub = QTableWidgetItem(f"${sub:.2f}")
            i_sub.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            self.table.setItem(r, 0, i_id)
            self.table.setItem(r, 1, i_nom)
            self.table.setItem(r, 2, i_can)
            self.table.setItem(r, 3, i_cos)
            self.table.setItem(r, 4, i_sub)

        self.lbl_total.setText(f"Total Factura: ${total:.2f}")
        self.table.itemChanged.connect(self.recalcular_totales)

    def recalcular_totales(self, item):
        row = item.row()
        col = item.column()

        if col in [2, 3]:
            try:
                val = float(item.text().replace(',', '.'))
                if val < 0: val = 0.0

                if col == 2:
                    self.carrito[row]['cantidad'] = val
                else:
                    self.carrito[row]['costo'] = val

                self.render_carrito()
            except ValueError:
                self.render_carrito()

    def procesar_compra(self):
        if not self.carrito:
            QMessageBox.warning(self, "Vacío", "No hay productos en el ingreso.")
            return

        prov_id = self.combo_proveedor.currentData()
        if not prov_id:
            QMessageBox.warning(self, "Error", "Debe seleccionar un Proveedor válido.")
            return

        num_fac = self.txt_factura.text().strip()
        if not num_fac:
            QMessageBox.warning(self, "Error", "Debe indicar el Nº de Factura.")
            return

        total_float = sum(i['cantidad']*i['costo'] for i in self.carrito)

        reply = QMessageBox.question(
            self, "Confirmar Ingreso",
            f"Se registrará la compra por ${total_float:.2f}\nEl stock será actualizado matemáticamente.\n¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                detalles = []
                for i in self.carrito:
                    detalles.append({
                        'producto_id': i['id'],
                        'cantidad': i['cantidad'],
                        'nuevo_costo': i['costo']
                    })

                ComprasService.ingresar_factura_compra(prov_id, num_fac, detalles, total_float)
                QMessageBox.information(self, "Éxito", "Factura procesada. Stock y Costos actualizados.")

                # Reset
                self.carrito = []
                self.txt_factura.clear()
                self.render_carrito()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

class ImportacionListasTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.df = None
        self.filas_preview = []

        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # Contenedor superior (Carga y Mapeo)
        self.top_widget = QWidget()
        from PyQt6.QtWidgets import QSizePolicy
        self.top_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.top_layout = QVBoxLayout(self.top_widget)
        self.top_layout.setContentsMargins(0, 0, 0, 0)

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
        self.top_layout.addWidget(self.import_group)

        # Contenedor inferior (Previsualización)
        self.bottom_widget = QWidget()
        self.bottom_layout = QVBoxLayout(self.bottom_widget)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)

        # --- ZONA DE PREVISUALIZACIÓN Y APROBACIÓN ---
        self.preview_group = QGroupBox("Previsualización de Cambios (Por Impactar)")
        self.preview_layout = QVBoxLayout()

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels([
            "SKU Interno", "Nombre", "Proveedor", "Costo Anterior", "Costo Nuevo"
        ])

        # Ergonomía: Columnas interactivas
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setColumnWidth(0, 150)
        self.tabla.setColumnWidth(1, 300)
        self.tabla.setColumnWidth(2, 150)

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
        self.bottom_layout.addWidget(self.preview_group)

        self.splitter.addWidget(self.top_widget)
        self.splitter.addWidget(self.bottom_widget)
        self.splitter.setSizes([250, 450])

        self.layout.addWidget(self.splitter)

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


class ProveedoresView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.tab_sugerencias = SugerenciasTab()
        self.tab_compras = IngresoFacturaTab()

        self.tabs.addTab(self.tab_sugerencias, "Sugerencias y Pedidos")
        self.tabs.addTab(self.tab_compras, "Facturas de Compra (Ingreso de Stock)")
        self.tab_import = ImportacionListasTab()
        self.tabs.addTab(self.tab_import, "Importación de Listas")

        layout.addWidget(self.tabs)

    def showEvent(self, event):
        super().showEvent(event)
        self.tab_sugerencias.cargar_datos()
        self.tab_compras.cargar_datos_base()
