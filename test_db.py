import sqlite3
import pandas as pd
from unificador_listas.app import App
import os

# Create dummy master DB
conn = sqlite3.connect("master.db")
c = conn.cursor()
c.execute("CREATE TABLE productos_maestro (sku_interno TEXT, proveedor TEXT, codigo_proveedor TEXT, descripcion TEXT, marca TEXT, costo_neto REAL)")
c.execute("INSERT INTO productos_maestro VALUES ('SKU1', 'PROV1', 'COD1', 'Desc1', 'Marca1', 100.0)")
conn.commit()
conn.close()

# Test app initialization and config
with open("config.json", "w") as f:
    f.write('{"master_db_path": "master.db"}')

# We can't easily start the UI without Xvfb, but we can verify it initializes the local db and loads the master db via config
