import sys
import os
import pandas as pd
from datetime import datetime

# Setup path
sys.path.insert(0, os.path.abspath('lubricentro'))

from db import SessionLocal
from db.models.productos import Producto, Marca
from db.models.proveedores import Proveedor
from proveedores.import_listas import ImportWorker

# Create mock data
df = pd.DataFrame({
    'sku_interno': ['NEW-001', 'MARCAX-002', 'NEW-001'], # The last one should update the first
    'proveedor': ['Prov Test 1', 'Prov Test 2', 'Prov Test 1'],
    'codigo_proveedor': ['P1-A', 'P2-B', 'P1-A-MOD'],
    'marca': ['Marca Test 1', 'Marca Test 2', 'Marca Test 1'],
    'descripcion': ['Desc 1', 'Desc 2', 'Desc 1 Modificada'],
    'costo_neto': [100.0, 200.0, 150.0],
    'contenido_caja': [1, 5, 1],
    'fecha_actualizacion': ['2023-01-01', '2023-01-01', '2023-01-02']
})
df.to_excel('mock_maestro.xlsx', index=False)

# Empty the tables for the test to ensure clean state
with SessionLocal() as s:
    s.query(Producto).filter(Producto.sku.in_(['NEW-001', 'MARCAX-002'])).delete(synchronize_session=False)
    s.query(Proveedor).filter(Proveedor.nombre.in_(['Prov Test 1', 'Prov Test 2'])).delete(synchronize_session=False)
    s.query(Marca).filter(Marca.nombre.in_(['Marca Test 1', 'Marca Test 2'])).delete(synchronize_session=False)
    s.commit()

# Create dummy app needed for QThread
from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)

worker = ImportWorker('mock_maestro.xlsx')
actualizados = 0
nuevos = 0

def on_finished(a, n):
    global actualizados, nuevos
    actualizados = a
    nuevos = n

worker.finished_import.connect(on_finished)
worker.run() # Run synchronously for testing

with SessionLocal() as s:
    prod_1 = s.query(Producto).filter_by(sku='NEW-001').first()
    prod_2 = s.query(Producto).filter_by(sku='MARCAX-002').first()
    prov_1 = s.query(Proveedor).filter_by(nombre='Prov Test 1').first()
    marca_1 = s.query(Marca).filter_by(nombre='Marca Test 1').first()

    print(f"Nuevos reportados por worker: {nuevos}")
    print(f"Actualizados reportados por worker: {actualizados}")
    print(f"Producto 1 existe: {prod_1 is not None}")
    if prod_1:
        print(f"Producto 1 costo: {prod_1.costo} (Debe ser 150.0)")
        print(f"Producto 1 descripcion: {prod_1.nombre} (Ojo: UPSERT estricto no actualiza desc, solo inserts. Aqui el insert lo creó con 'Desc 1')")
        print(f"Producto 1 prov_id: {prod_1.proveedor_id} == {prov_1.id if prov_1 else None}")
        print(f"Producto 1 marca_id: {prod_1.marca_id} == {marca_1.id if marca_1 else None}")

    print(f"Producto 2 existe: {prod_2 is not None}")
