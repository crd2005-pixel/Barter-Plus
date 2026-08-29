import datetime
import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox,
    QLabel, QProgressDialog, QTableWidget, QTableWidgetItem, QComboBox, QFormLayout, QGroupBox, QHeaderView
)
from PyQt5.QtCore import Qt
from db import SessionLocal
from db.models.productos import Producto, Marca
from db.models.proveedores import Proveedor

class ImportadorMaestroTab(QWidget):
    def __init__(self, on_after_import=None):
        super().__init__()
        self.on_after_import = on_after_import
        self.df_actual = None
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)

        # 1. Selección de archivo
        box_archivo = QHBoxLayout()
        self.btn_cargar = QPushButton("Cargar Excel / Maestro")
        self.btn_cargar.clicked.connect(self._cargar_archivo)
        self.lbl_archivo = QLabel("Ningún archivo seleccionado")
        box_archivo.addWidget(self.btn_cargar)
        box_archivo.addWidget(self.lbl_archivo)
        box_archivo.addStretch()
        lay.addLayout(box_archivo)

        # 2. Mapeo de columnas
        self.grp_mapeo = QGroupBox("Mapeo de Columnas")
        form_mapeo = QFormLayout()

        self.map_sku = QComboBox()
        self.map_proveedor = QComboBox()
        self.map_codigo = QComboBox()
        self.map_marca = QComboBox()
        self.map_desc = QComboBox()
        self.map_costo = QComboBox()
        self.map_caja = QComboBox()

        form_mapeo.addRow("SKU Interno (Único)*:", self.map_sku)
        form_mapeo.addRow("Proveedor*:", self.map_proveedor)
        form_mapeo.addRow("Código Proveedor:", self.map_codigo)
        form_mapeo.addRow("Marca:", self.map_marca)
        form_mapeo.addRow("Descripción*:", self.map_desc)
        form_mapeo.addRow("Costo Neto*:", self.map_costo)
        form_mapeo.addRow("Contenido Caja:", self.map_caja)

        self.grp_mapeo.setLayout(form_mapeo)
        self.grp_mapeo.setEnabled(False)
        lay.addWidget(self.grp_mapeo)

        # 3. Vista Previa
        self.tbl_preview = QTableWidget()
        self.tbl_preview.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        lay.addWidget(QLabel("Vista Previa (50 filas):"))
        lay.addWidget(self.tbl_preview)

        # 4. Importar
        self.btn_importar = QPushButton("Importar a Base de Datos")
        self.btn_importar.clicked.connect(self._importar_datos)
        self.btn_importar.setEnabled(False)
        self.btn_importar.setMinimumHeight(40)
        self.btn_importar.setStyleSheet("font-weight: bold; background-color: #2E7D32; color: white;")
        lay.addWidget(self.btn_importar)

    def _cargar_archivo(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Archivo", "", "Excel Files (*.xlsx *.xls *.csv)"
        )
        if not ruta:
            return

        try:
            self.lbl_archivo.setText(ruta)
            if ruta.endswith('.csv'):
                self.df_actual = pd.read_csv(ruta)
            else:
                self.df_actual = pd.read_excel(ruta)

            # Limpiar nombres de columnas
            self.df_actual.columns = [str(c).strip() for c in self.df_actual.columns]

            self._actualizar_combos()
            self._mostrar_vista_previa()

            self.grp_mapeo.setEnabled(True)
            self.btn_importar.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Error al leer", f"No se pudo leer el archivo:\n{e}")

    def _actualizar_combos(self):
        columnas = ["(Ignorar)"] + list(self.df_actual.columns)

        combos = [
            (self.map_sku, ["sku_interno", "sku", "id", "codigo interno"]),
            (self.map_proveedor, ["proveedor", "distribuidor", "prov"]),
            (self.map_codigo, ["codigo_proveedor", "codigo", "cod", "cod_prov"]),
            (self.map_marca, ["marca", "brand"]),
            (self.map_desc, ["descripcion", "nombre", "articulo", "producto", "desc"]),
            (self.map_costo, ["costo_neto", "precio", "costo", "precio unitario"]),
            (self.map_caja, ["contenido_caja", "unidades", "pack", "caja"])
        ]

        for combo, keywords in combos:
            combo.clear()
            combo.addItems(columnas)

            # Auto-selección inteligente
            encontrado = False
            for col in self.df_actual.columns:
                col_lower = col.lower()
                if any(kw in col_lower for kw in keywords):
                    combo.setCurrentText(col)
                    encontrado = True
                    break

            if not encontrado:
                combo.setCurrentIndex(0) # (Ignorar)

    def _mostrar_vista_previa(self):
        if self.df_actual is None: return

        df_head = self.df_actual.head(50)
        self.tbl_preview.clear()
        self.tbl_preview.setColumnCount(len(df_head.columns))
        self.tbl_preview.setRowCount(len(df_head))
        self.tbl_preview.setHorizontalHeaderLabels(list(df_head.columns))

        for row_idx, row in df_head.iterrows():
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(str(value) if pd.notna(value) else "")
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.tbl_preview.setItem(row_idx, col_idx, item)

    def _limpiar_precio(self, valor):
        if pd.isna(valor) or valor == "": return 0.0
        if isinstance(valor, (int, float)): return float(valor)

        # Limpiar strings tipo "$ 1.500,50" -> 1500.50
        v = str(valor).replace('$', '').replace(' ', '')
        # Si tiene punto de miles y coma decimal
        if '.' in v and ',' in v:
            if v.rfind(',') > v.rfind('.'):
                v = v.replace('.', '').replace(',', '.')
            else:
                v = v.replace(',', '')
        elif ',' in v:
            v = v.replace(',', '.')

        try:
            return float(v)
        except:
            return 0.0

    def _importar_datos(self):
        if self.df_actual is None: return

        # Validar campos obligatorios
        c_sku = self.map_sku.currentText()
        c_prov = self.map_proveedor.currentText()
        c_desc = self.map_desc.currentText()
        c_costo = self.map_costo.currentText()

        obligatorios = []
        if c_sku == "(Ignorar)": obligatorios.append("SKU Interno")
        if c_prov == "(Ignorar)": obligatorios.append("Proveedor")
        if c_desc == "(Ignorar)": obligatorios.append("Descripción")
        if c_costo == "(Ignorar)": obligatorios.append("Costo Neto")

        if obligatorios:
            QMessageBox.warning(self, "Faltan Columnas", f"Debe mapear los siguientes campos obligatorios:\n{', '.join(obligatorios)}")
            return

        c_codigo = self.map_codigo.currentText()
        c_marca = self.map_marca.currentText()
        c_caja = self.map_caja.currentText()

        progreso = QProgressDialog("Importando y actualizando base de datos...", "Cancelar", 0, len(self.df_actual), self)
        progreso.setWindowModality(2)

        nuevos = 0
        actualizados = 0
        errores = 0

        with SessionLocal() as s:
            for idx, row in self.df_actual.iterrows():
                if progreso.wasCanceled(): break
                progreso.setValue(idx)

                try:
                    sku = str(row[c_sku]).strip()
                    if pd.isna(row[c_sku]) or not sku: continue

                    prov_nombre = str(row[c_prov]).strip()
                    desc = str(row[c_desc]).strip()
                    costo = self._limpiar_precio(row[c_costo])

                    cod_prov = str(row[c_codigo]).strip() if c_codigo != "(Ignorar)" and pd.notna(row[c_codigo]) else ""
                    marca_nombre = str(row[c_marca]).strip() if c_marca != "(Ignorar)" and pd.notna(row[c_marca]) else ""

                    try:
                        cont_caja = float(row[c_caja]) if c_caja != "(Ignorar)" and pd.notna(row[c_caja]) else 1.0
                    except:
                        cont_caja = 1.0

                    # 1. Resolver Proveedor
                    prov = s.query(Proveedor).filter_by(nombre=prov_nombre).first()
                    if not prov:
                        prov = Proveedor(nombre=prov_nombre)
                        s.add(prov)
                        s.flush()

                    # 2. Resolver Marca
                    marca_id = None
                    if marca_nombre and marca_nombre.lower() != "nan":
                        marca = s.query(Marca).filter_by(nombre=marca_nombre).first()
                        if not marca:
                            marca = Marca(nombre=marca_nombre)
                            s.add(marca)
                            s.flush()
                        marca_id = marca.id

                    # 3. UPSERT Producto
                    prod = s.query(Producto).filter_by(sku=sku).first()

                    if prod:
                        prod.costo = costo
                        prod.proveedor_id = prov.id
                        if cod_prov: prod.codigo_proveedor = cod_prov
                        if marca_id: prod.marca_id = marca_id
                        prod.nombre = desc
                        prod.presentacion_cantidad = cont_caja
                        prod.actualizado_en = datetime.datetime.now()
                        actualizados += 1
                    else:
                        prod = Producto(
                            sku=sku,
                            nombre=desc,
                            costo=costo,
                            proveedor_id=prov.id,
                            codigo_proveedor=cod_prov,
                            marca_id=marca_id,
                            presentacion_cantidad=cont_caja,
                            actualizado_en=datetime.datetime.now()
                        )
                        s.add(prod)
                        nuevos += 1
                except Exception as e:
                    errores += 1
                    print(f"Error en fila {idx}: {e}")

            s.commit()
            progreso.setValue(len(self.df_actual))

        msg = f"Importación completada.\n\nNuevos creados: {nuevos}\nActualizados: {actualizados}\nErrores omitidos: {errores}"
        QMessageBox.information(self, "Éxito", msg)

        # Limpiar UI
        self.df_actual = None
        self.lbl_archivo.setText("Ningún archivo seleccionado")
        self.tbl_preview.clear()
        self.grp_mapeo.setEnabled(False)
        self.btn_importar.setEnabled(False)

        if self.on_after_import:
            self.on_after_import()
