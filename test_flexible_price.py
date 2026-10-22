from unificador_listas.app import App
import numpy as np

app = App()

row1 = ["WK6002\n$4.434", "C31003/1", "FAP4046/1"]
ctx1, ext1 = app._process_heuristic_row(row1, "", "PROV", "hoja1")
for item in ext1:
    print(f"Cod: {item['codigo_proveedor']} | Desc: {item['descripcion']} | Price: {item['costo_neto']}")

row2 = ["12X45", "WILLARD", "ford k fiesta", "205", "175", "190", "$ 105.361", "$ 117.878", "$ 97.111"]
ctx2, ext2 = app._process_heuristic_row(row2, "BATTERY", "PROV", "hoja1")
for item in ext2:
    print(f"Cod: {item['codigo_proveedor']} | Desc: {item['descripcion']} | Price: {item['costo_neto']}")
