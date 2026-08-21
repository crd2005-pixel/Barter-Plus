import datetime
import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QMessageBox, QLabel, QProgressDialog
)
from db import SessionLocal
from db.models.productos import Producto, Marca
from db.models.proveedores import Proveedor

class ImportadorMaestroTab(QWidget):
    def __init__(self, on_after_import=None):
        super().__init__()
        self.on_after_import = on_after_import
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        self.lbl_info = QLabel("Seleccione el archivo 'Inventario_Maestro_Unificado.xlsx' para importar/actualizar.")
        lay.addWidget(self.lbl_info)

        self.btn_importar = QPushButton("Importar Maestro Unificado")
        self.btn_importar.clicked.connect(self._importar)
        lay.addWidget(self.btn_importar)
        lay.addStretch()

    def _importar(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Maestro Unificado", "", "Excel Files (*.xlsx *.xls)"
        )
        if not ruta:
            return

        try:
            df = pd.read_excel(ruta)
            columnas_requeridas = {
                "sku_interno", "proveedor", "codigo_proveedor", "marca",
                "descripcion", "costo_neto", "contenido_caja", "fecha_actualizacion"
            }
            if not columnas_requeridas.issubset(set(df.columns)):
                faltan = columnas_requeridas - set(df.columns)
                QMessageBox.warning(self, "Error", f"El archivo no tiene el formato correcto. Faltan columnas: {faltan}")
                return

            self._procesar_df(df)

        except Exception as e:
            QMessageBox.critical(self, "Error al leer", f"No se pudo leer el archivo:\n{e}")

    def _procesar_df(self, df):
        progreso = QProgressDialog("Procesando inventario...", "Cancelar", 0, len(df), self)
        progreso.setWindowModality(2) # Qt.WindowModal

        nuevos = 0
        actualizados = 0

        with SessionLocal() as s:
            for idx, row in df.iterrows():
                if progreso.wasCanceled():
                    break
                progreso.setValue(idx)

                sku = str(row["sku_interno"]).strip()
                prov_nombre = str(row["proveedor"]).strip()
                cod_prov = str(row["codigo_proveedor"]).strip()
                marca_nombre = str(row["marca"]).strip()
                desc = str(row["descripcion"]).strip()
                try:
                    costo = float(row["costo_neto"])
                except:
                    costo = 0.0

                try:
                    cont_caja = float(row["contenido_caja"])
                except:
                    cont_caja = 1.0

                # Obtener o crear proveedor
                prov = s.query(Proveedor).filter_by(nombre=prov_nombre).first()
                if not prov:
                    prov = Proveedor(nombre=prov_nombre)
                    s.add(prov)
                    s.flush()

                # Obtener o crear marca
                marca_id = None
                if marca_nombre and marca_nombre.lower() != "nan":
                    marca = s.query(Marca).filter_by(nombre=marca_nombre).first()
                    if not marca:
                        marca = Marca(nombre=marca_nombre)
                        s.add(marca)
                        s.flush()
                    marca_id = marca.id

                # Buscar producto por SKU interno (identificador único del maestro)
                prod = s.query(Producto).filter_by(sku=sku).first()

                if prod:
                    prod.costo = costo
                    prod.proveedor_id = prov.id
                    prod.codigo_proveedor = cod_prov
                    prod.marca_id = marca_id
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

            s.commit()
            progreso.setValue(len(df))

        msg = f"Importación completada.\nNuevos: {nuevos}\nActualizados: {actualizados}"
        QMessageBox.information(self, "Éxito", msg)

        if self.on_after_import:
            self.on_after_import()
