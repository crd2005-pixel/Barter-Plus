import os
import sqlite3
import unittest
import ast
import tempfile

class TestUnificadorLocal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp()
        os.environ['APPDATA'] = cls.test_dir
        cls.db_dir = os.path.join(cls.test_dir, 'BarterPlus')
        os.makedirs(cls.db_dir, exist_ok=True)
        cls.db_path = os.path.join(cls.db_dir, 'barterplus.db')
        conn = sqlite3.connect(cls.db_path)
        conn.execute("CREATE TABLE productos (id INTEGER PRIMARY KEY, codigo_proveedor TEXT, descripcion TEXT, marca TEXT, proveedor TEXT, equivalencias TEXT)")
        conn.execute("INSERT INTO productos (codigo_proveedor, descripcion, marca, proveedor, equivalencias) VALUES ('123', 'TEST A', 'MARCA1', 'PROV1', '')")
        conn.commit()
        conn.close()

    def test_file_size_and_content(self):
        file_path = os.path.join(os.path.dirname(__file__), 'main.py')
        self.assertTrue(os.path.exists(file_path))
        size = os.path.getsize(file_path)
        self.assertGreater(size, 25000)

    def test_conversion_markdown_sin_desfase_baterias(self):
        from unificador_listas.main import MotorCruceBarterPlus
        motor = MotorCruceBarterPlus(db_path=self.db_path)

        # Simula filas crudas con desfase
        filas = [
            ["M40FD", "12X40", "MOURA", "AGILE"],
            ["M18FD", "12X50", "MOURA", "FIORINO"],
            ["", "", "", "", "$ 109.628"],
            ["", "", "", "", "$ 122.262"]
        ]

        md = motor.convertir_origen_a_markdown(filas)

        # M40FD should align with $ 109.628
        self.assertIn("| M40FD | 12X40 | MOURA | AGILE | $ 109.628 |", md)
        self.assertIn("| M18FD | 12X50 | MOURA | FIORINO | $ 122.262 |", md)

    def test_parseo_desde_markdown_editado_y_reglas(self):
        from unificador_listas.main import MotorCruceBarterPlus
        motor = MotorCruceBarterPlus(db_path=self.db_path)

        md_editado = """| Fila | Col 0 [CÓDIGO] | Col 1 [DESC] | Col 2 [MARCA] | Col 3 [APLICACIÓN] | Col 9 [PRECIO] |
|---|---|---|---|---|---|
| 1 | DL 450 | 12X50 | LEMOM | FORD K | $ 67.338 |
| 2 | WK6002 | FILTRO | SEINECA | | $ 4.434 |
"""

        prods = motor.parsear_desde_markdown(md_editado)
        self.assertEqual(len(prods), 2)
        self.assertEqual(prods[0]["codigo_proveedor"], "DL 450")
        self.assertEqual(prods[0]["costo"], 67338.0)

        self.assertEqual(prods[1]["codigo_proveedor"], "WK6002")
        self.assertEqual(prods[1]["costo"], 4.43) # Note: 4.434 -> 4.43

if __name__ == '__main__':
    unittest.main()
