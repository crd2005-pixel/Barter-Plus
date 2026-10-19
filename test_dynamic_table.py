from unificador_listas.app import App
import sqlite3
import os

# Create dummy DB with non-standard table name
conn = sqlite3.connect("test_dynamic.db")
c = conn.cursor()
c.execute("CREATE TABLE mi_inventario_loco (codigo TEXT, detalle TEXT, costo REAL)")
c.execute("INSERT INTO mi_inventario_loco VALUES ('123', 'Prod Test', 150.0)")
conn.commit()
conn.close()

app = App()
app.load_master_index_db("test_dynamic.db")

print(f"Table found: {app.last_master_table_name}")
print(f"Items in desc map: {list(app.mapa_por_descripcion.keys())}")
