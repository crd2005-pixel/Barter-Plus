import unittest
import os
import sys

# Ajuste temporal del sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if os.path.dirname(current_dir) not in sys.path:
    sys.path.insert(0, os.path.dirname(current_dir))

from unificador_listas.src.database import get_unificador_dir, get_barterplus_db_path, registrar_error_seguro
from unificador_listas.src.parser_pdf import limpiar_precio, _parse_baterias_table, _parse_seineca_table
from unificador_listas.src.ai_engine import fallback_ia_a_determinista

class TestUnificadorListas(unittest.TestCase):

    def test_rutas_seguras(self):
        # Regla 2 y Falla 1: Falla de Rutas Relativas
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        expected_dir = os.path.join(appdata, "BarterPlus_Unificador")
        self.assertEqual(get_unificador_dir(), expected_dir)

        # Test error log creation without crashing
        registrar_error_seguro("Test de error seguro")
        log_path = os.path.join(expected_dir, "error_log.txt")
        self.assertTrue(os.path.exists(log_path))

    def test_db_path(self):
        # Regla 1
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        expected_db = os.path.join(appdata, "BarterPlus", "barterplus.db")
        self.assertEqual(get_barterplus_db_path(), expected_db)

    def test_limpiar_precio(self):
        self.assertEqual(limpiar_precio("105361"), 105361.0)
        self.assertEqual(limpiar_precio("$ 105.361"), 105361.0)
        self.assertEqual(limpiar_precio("1.500,50"), 1500.50)
        self.assertEqual(limpiar_precio("1500,50"), 1500.50)
        self.assertEqual(limpiar_precio("1,500.50"), 1500.50)

    def test_candado_datos(self):
        # Regla 3: Candado de Datos
        # Simulamos salida de la tabla baterías para verificar que no haya $ en cod
        row = ["$\n$ 113.873", "12X45", "WILLARD", "ford", "205", "175", "190", "$ 113.873", "", "$ 113.873"]
        table = [["CÓDIGO", "AMP", "MARCA", "APP", "L", "A", "AL", "C", "V", "F"], row]
        productos = _parse_baterias_table(table, {"baterias_precio_col": "FINAL C/USADA"})
        # No debe haber extraído producto válido si el código es $
        self.assertEqual(len(productos), 0)

    def test_seineca_format(self):
        # Falla 3: Falla en PDF "Seineca"
        # CÓDIGO (0) | DESCRIPCIÓN (1) | PRECIO (2) | MANN (3) | FRAM (4) | WEGA (5) | MARENO (6)
        table = [
            [None, "FILTROS DE ACEITE"],
            ["SFF32205", "FILTRO ACEITE", "$4.434", "W712", "PH3593A", "JFO0101", ""],
            ["WK6002\n$4.434", "FILTRO COMBUSTIBLE", "", "", "", "", ""] # Simulación de celda multilínea fusionada por pdfplumber
        ]
        productos = _parse_seineca_table(table)
        self.assertEqual(len(productos), 2)

        self.assertEqual(productos[0]["codigo_proveedor"], "SFF32205")
        self.assertIn("MANN: W712", productos[0]["descripcion"])
        self.assertEqual(productos[0]["costo"], 4434.0)

        self.assertEqual(productos[1]["codigo_proveedor"], "WK6002")
        self.assertEqual(productos[1]["costo"], 4434.0)

    def test_baterias_format(self):
        # Falla 4: Falla en PDF "La Casa de las Baterías"
        table = [
            ["CÓDIGO", "AMP. COMERCIAL", "MARCA", "PRINCIPAL APLICACIÓN", "LARGO", "ANCHO", "ALTO", "COSTO S/USADA", "VALOR USADA", "FINAL C/USADA"],
            ["UB 450\nM40FD", "12X45\n12X40", "WILLARD\nMOURA", "ford k fiesta", "205", "175", "190", "$ 100.000\n$ 110.000", "", "$ 105.000\n$ 115.000"]
        ]
        productos = _parse_baterias_table(table, {"baterias_precio_col": "FINAL C/USADA"})
        self.assertEqual(len(productos), 2)
        self.assertEqual(productos[0]["codigo_proveedor"], "UB 450")
        self.assertEqual(productos[0]["costo"], 105000.0)
        self.assertEqual(productos[0]["marca"], "WILLARD")

        self.assertEqual(productos[1]["codigo_proveedor"], "M40FD")
        self.assertEqual(productos[1]["costo"], 115000.0)
        self.assertEqual(productos[1]["marca"], "MOURA")

    def test_fallback_ia(self):
        # Falla 5: Falla Silenciosa de 2 Segundos
        def fail_ia():
            raise ValueError("API Error")

        def mock_ia_empty():
            return []

        def mock_ia_dict():
            return {"productos": [{"codigo_proveedor": "123", "descripcion": "TEST", "marca": "M", "costo": 10.0}]}

        def mock_det():
            return [{"codigo_proveedor": "DET", "descripcion": "TEST_DET", "marca": "M", "costo": 20.0}]

        res1 = fallback_ia_a_determinista(fail_ia, mock_det)
        self.assertEqual(res1[0]["codigo_proveedor"], "DET")

        res2 = fallback_ia_a_determinista(mock_ia_empty, mock_det)
        self.assertEqual(res2[0]["codigo_proveedor"], "DET")

        res3 = fallback_ia_a_determinista(mock_ia_dict, mock_det)
        self.assertEqual(res3[0]["codigo_proveedor"], "123")

    def test_doble_candado_colision(self):
        # Falla 6: Colisión de Códigos Cortos entre Rubros Distintos
        from unificador_listas.src.core_logic import validar_colision

        # Simular base de datos (por_sku, por_cod_prov, por_descripcion)
        # Hay un radiador con código corto "10" del proveedor "RAD"
        indices = (
            {}, # por_sku
            {"10": [("RAD-10", "10", "RADIADOR SUPERIOR FIAT", "VALEO")]}, # por_cod_prov
            {} # por_desc
        )

        # 1. Mismo proveedor (Actualización permitida)
        res1 = validar_colision("10", "RADIADOR FIAT", "RAD", indices)
        self.assertEqual(res1, "ACTUALIZACION")

        # 2. Distinto proveedor pero coincidencia semántica (Actualización permitida)
        res2 = validar_colision("10", "RADIADOR SUPERIOR M. MARELLI", "OTRO", indices)
        self.assertEqual(res2, "ACTUALIZACION")

        # 3. Distinto proveedor y sin coincidencia semántica (Colisión Falla 6 -> NUEVO)
        res3 = validar_colision("10", "PERFUME VAINILLA CHICO", "PERF", indices)
        self.assertEqual(res3, "NUEVO")

if __name__ == '__main__':
    unittest.main()
