import unittest
import os
import shutil
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db import Base, Producto
from services.actualizacion_precios import procesar_actualizacion_precios

class TestActualizacionPrecios(unittest.TestCase):
    def setUp(self):
        # Create a temporary sqlite database on disk to avoid sharing issues between connections
        self.db_path = "test_actualizacion_precios.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        self.engine = create_engine(f'sqlite:///{self.db_path}')
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Override the SessionLocal in actualizacion_precios and utils
        from services import actualizacion_precios
        self.orig_session = getattr(actualizacion_precios, "SessionLocal", None)
        actualizacion_precios.SessionLocal = self.SessionLocal

        import productos.utils
        self.orig_utils_session = getattr(productos.utils, "SessionLocal", None)
        productos.utils.SessionLocal = self.SessionLocal

        # Populate DB with some sample products and config params
        from db.models.params import ConfigParam
        with self.SessionLocal() as session:
            # ConfigParams defaults mapped in utils.py
            c1 = ConfigParam(clave="margen_lubricantes", valor="35.0")
            c2 = ConfigParam(clave="margen_baterias", valor="35.0")
            p1 = Producto(sku="123", codigo_barras="BAR123", nombre="Producto 1 exact match", rubro="Lubricantes", costo=100.0, iva=21.0)
            p2 = Producto(sku="456", codigo_barras="BAR456", nombre="Producto 2 con typo exacto", rubro="Baterias", costo=50.0, iva=10.5)
            session.add_all([c1, c2, p1, p2])
            session.commit()

        # Set up temporary directories for files
        self.test_dir = "test_actualizacion"
        os.makedirs(self.test_dir, exist_ok=True)
        self.listas_dir = os.path.join(self.test_dir, "listas")
        os.makedirs(self.listas_dir, exist_ok=True)

        # Create the equivalences Excel file
        self.ruta_equiv = os.path.join(self.test_dir, "equiv.xlsx")
        df_equiv = pd.DataFrame({
            "Codigo_Proveedor": ["PROV-01", "PROV-02"],
            "SKU_Interno": ["123", "BAR456"] # Using SKU for first, Barcode for second
        })
        df_equiv.to_excel(self.ruta_equiv, index=False)

        # Create a new price list Excel file using a custom template/sheet
        self.ruta_lista = os.path.join(self.listas_dir, "lista_nueva.xlsx")
        df_prov = pd.DataFrame({
            "My_Supplier_Code": ["PROV-01", "PROV-UNKNOWN", ""],
            "Item_Description": ["Prod 1 exact match", "Unrecognized string", "Producto 2 con typo exacto (fuzzy match base)"], # 3rd row is for fuzzy matching
            "Price": [200.0, 999.0, 75.0],
            "Image": ["img1.png", "img2.png", "img3.png"] # dummy extra col
        })
        # write to a specific sheet to test config
        with pd.ExcelWriter(self.ruta_lista) as writer:
            df_prov.to_excel(writer, sheet_name="Tab_Promocional", index=False)

        self.config_proveedores = {
            "lista_nueva.xlsx": {
                "sheet_name": "Tab_Promocional",
                "col_code": "My_Supplier_Code",
                "col_desc": "Item_Description",
                "col_cost": "Price"
            }
        }

    def tearDown(self):
        # Restore SessionLocal
        from services import actualizacion_precios
        if self.orig_session:
            actualizacion_precios.SessionLocal = self.orig_session

        import productos.utils
        if self.orig_utils_session:
            productos.utils.SessionLocal = self.orig_utils_session

        # Clean up files
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_procesar_actualizacion_precios(self):
        # Let's override actual db to ensure they point to the exact same engine/connection in memory
        from db import SessionLocal as db_SessionLocal
        orig_db_session = db_SessionLocal
        import db
        db.SessionLocal = self.SessionLocal

        import services.actualizacion_precios as sap
        sap.SessionLocal = self.SessionLocal

        # Reset log file
        log_path = "unmatched_review_queue.log"
        if os.path.exists(log_path):
            os.remove(log_path)

        archivos_procesados = procesar_actualizacion_precios(self.ruta_equiv, self.listas_dir, self.config_proveedores)
        self.assertEqual(archivos_procesados, 1)

        db.SessionLocal = orig_db_session
        sap.SessionLocal = getattr(self, "orig_session", None)

        with self.SessionLocal() as session:
            p1 = session.query(Producto).filter(Producto.sku == "123").first()
            self.assertIsNotNone(p1)
            self.assertEqual(p1.costo, 200.0)
            # From db, margen_lubricantes defaults to 35.0
            # Formula: (costo * (1 + iva)) / (1 - margen) -> (200.0 * 1.21) / (1 - 0.35) = 242.0 / 0.65 = 372.3076... -> round 2 = 372.31
            self.assertAlmostEqual(p1.precio_minorista, 372.31, places=2)

            p2 = session.query(Producto).filter(Producto.codigo_barras == "BAR456").first()
            self.assertIsNotNone(p2)
            self.assertEqual(p2.costo, 75.0)
            # From db, margen_baterias defaults to 35.0
            # Formula: (costo * (1 + iva)) / (1 - margen) -> (75.0 * 1.105) / (1 - 0.35) = 82.875 / 0.65 = 127.5
            self.assertAlmostEqual(p2.precio_minorista, 127.5, places=2)

        # Check logs for skipped item
        self.assertTrue(os.path.exists(log_path))
        with open(log_path, 'r') as f:
            logs = f.read()
            self.assertIn("Unrecognized string", logs)

if __name__ == "__main__":
    unittest.main()
