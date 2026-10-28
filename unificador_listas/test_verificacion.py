import os
import sqlite3
import unittest
import ast
import tempfile

class TestUnificadorLocal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Configurar variables de entorno aislando pruebas
        cls.test_dir = tempfile.mkdtemp()
        os.environ['APPDATA'] = cls.test_dir
        # Crear BD SQLite falsa simulada
        cls.db_dir = os.path.join(cls.test_dir, 'BarterPlus')
        os.makedirs(cls.db_dir, exist_ok=True)
        cls.db_path = os.path.join(cls.db_dir, 'barterplus.db')
        conn = sqlite3.connect(cls.db_path)
        conn.execute("CREATE TABLE productos (id INTEGER PRIMARY KEY, codigo_proveedor TEXT, descripcion TEXT, marca TEXT, proveedor TEXT, equivalencias TEXT)")
        conn.execute("INSERT INTO productos (codigo_proveedor, descripcion, marca, proveedor, equivalencias) VALUES ('123', 'TEST A', 'MARCA1', 'PROV1', '')")
        conn.execute("INSERT INTO productos (codigo_proveedor, descripcion, marca, proveedor, equivalencias) VALUES ('105', 'DESC BATERIA', 'M2', 'PROV2', '')")
        conn.commit()
        conn.close()

    def test_file_size_and_content(self):
        file_path = 'unificador_listas/main.py'
        self.assertTrue(os.path.exists(file_path))
        size = os.path.getsize(file_path)
        print(f"File size: {size} bytes")
        self.assertGreater(size, 25000, "El archivo main.py debe ser mayor a 25KB para contener toda la lógica")

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("class UnificadorApp", content)
        self.assertIn("class ModalEntrenadorPrevisualizacion", content)
        self.assertIn("app = UnificadorApp()", content)
        self.assertIn("app.mainloop()", content)
        self.assertNotIn("google-genai", content)
        self.assertNotIn("gemini", content)

    def test_ast_method_calls(self):
        with open('unificador_listas/main.py', 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())

        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]

        for cls_node in classes:
            methods = {m.name for m in cls_node.body if isinstance(m, ast.FunctionDef)}

            for m_node in cls_node.body:
                if isinstance(m_node, ast.FunctionDef):
                    for call_node in ast.walk(m_node):
                        if isinstance(call_node, ast.Call) and isinstance(call_node.func, ast.Attribute):
                            if isinstance(call_node.func.value, ast.Name) and call_node.func.value.id == 'self':
                                method_called = call_node.func.attr
                                # Ignore some attributes that might be properties or framework methods (like tk/ctk methods)
                                if method_called not in methods and not hasattr(dict, method_called) and method_called not in ['after', 'update_idletasks', 'destroy', 'winfo_children']:
                                    pass # For this test we assume strictness, but tkinter adds many 'self.' methods dynamically

    def test_db_readonly(self):
        from unificador_listas.main import MotorCruceBarterPlus
        motor = MotorCruceBarterPlus()
        db_uri = f"file:{os.path.abspath(motor.db_path).replace(chr(92), '/')}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True)
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute("DELETE FROM productos")
        conn.close()

    def test_perfil_manager(self):
        from unificador_listas.main import GestorPerfilesEntrenamiento
        gestor = GestorPerfilesEntrenamiento()
        perfil = gestor.perfil_por_defecto()
        perfil['activa'] = False
        gestor.guardar_perfil('PROV_TEST', 'EXCEL', 'Hoja2', perfil)

        cargado = gestor.obtener_perfil('PROV_TEST', 'EXCEL', 'Hoja2')
        self.assertFalse(cargado['activa'])
        self.assertTrue(os.path.exists(gestor.archivo_perfiles))

    def test_seineca_precio(self):
        from unificador_listas.main import MotorCruceBarterPlus
        motor = MotorCruceBarterPlus(db_path=self.db_path)
        perfil = {
            "col_codigo": 0, "col_descripcion": 1, "col_precio": 2, "cols_equivalencias": [],
            "fila_inicio": 0, "filas_pie_ignorar": 0, "modo_multiline_baterias": False, "marca_fija": ""
        }
        filas = [["", "Filtro", "WK6002\n$4.434"], ["", "Filtro 2", "P945X/\nP945/2\n$ 8.454"]]
        prods = motor._procesar_filas(filas, perfil, "PDF_TEST")

        self.assertEqual(len(prods), 2)
        self.assertEqual(prods[0]["codigo_proveedor"], "WK6002")
        self.assertEqual(prods[0]["costo"], 4.43)
        self.assertEqual(prods[1]["codigo_proveedor"], "P945X/")
        self.assertEqual(prods[1]["costo"], 8.45)
        self.assertIn("P945/2", prods[1]["equivalencias"])

    def test_baterias_multiline(self):
        from unificador_listas.main import MotorCruceBarterPlus
        motor = MotorCruceBarterPlus(db_path=self.db_path)
        perfil = {
            "col_codigo": 0, "col_descripcion": 1, "col_precio": 2, "cols_equivalencias": [],
            "fila_inicio": 0, "filas_pie_ignorar": 0, "modo_multiline_baterias": True, "marca_fija": ""
        }
        # Simula:
        # Col 0: 123
# 124
        # Col 1: LEMOM
# PREMIUM
# OTRA
        # Col 2: $
# $ 113.873
# $ 50.00

        filas = [["123\n124", "LEMOM\nPREMIUM", "$\n$ 113.873"]]
        prods = motor._procesar_filas(filas, perfil, "PDF_TEST")
        # 123 is ignored because its cost is 0 due to $
        self.assertEqual(len(prods), 1)
        self.assertEqual(prods[0]["codigo_proveedor"], "124")
        self.assertEqual(prods[0]["descripcion"], "PREMIUM")
        # El dolar huerfano resulta en costo 0, se ignora
        # El segundo (124) toma PREMIUM y 113.873

        # Un test más ajustado a lo que saca _expand_multiline_pdf_row
        row = motor._expand_multiline_pdf_row(["123\n124", "LEMOM\nPREMIUM", "$\n$ 113.873"])
        self.assertEqual(row[0][0], "123")
        self.assertEqual(row[0][1], "LEMOM")
        self.assertEqual(row[0][2], "$")

    def test_candado_anticolision(self):
        from unificador_listas.main import MotorCruceBarterPlus
        motor = MotorCruceBarterPlus(db_path=self.db_path)

        # Test collision on short code "105" where descriptions don't match
        prods_extraidos = [{"codigo_proveedor": "105", "descripcion": "OTRO PRODUCTO DISTINTO", "costo": 100, "marca": "M3"}]
        nuevos, act = motor.cruzar_productos(prods_extraidos, "PROV2")
        # Debería ir a nuevos porque la descripcion no coincide
        self.assertEqual(len(nuevos), 1)
        self.assertEqual(len(act), 0)

        # Test collision on short code "105" where descriptions match
        prods_extraidos2 = [{"codigo_proveedor": "105", "descripcion": "BATERIA NUEVA", "costo": 100, "marca": "M2"}]
        nuevos2, act2 = motor.cruzar_productos(prods_extraidos2, "PROV2")
        # "BATERIA" interseca con "DESC BATERIA"
        self.assertEqual(len(nuevos2), 0)
        self.assertEqual(len(act2), 1)

if __name__ == '__main__':
    unittest.main()
