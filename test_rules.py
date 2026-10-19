from unificador_listas.app import App
import pandas as pd

app = App()

# Test cases:
# 1. Letterhead
print(app._process_heuristic_row(["Av. Sarmiento 263 - 5600 San Rafael - Mendoza"], "ABRAZADERAS", "PROV", "hoja1"))
# Expected: context_seccion remains "ABRAZADERAS"

# 2. Combined Titles
print(app._process_heuristic_row(["Standard Fleje 9mm"], "ABRAZADERAS PERFECTO", "PROV", "hoja1"))
# Expected: context_seccion "ABRAZADERAS PERFECTO - Standard Fleje 9mm"

# 3. Intermediate prices + duplication
# ["98-1045", "30- 45", 604.12, 845.76799, 1080.00]
_, ext = app._process_heuristic_row(["98-1045", "30- 45", 604.12, 845.76799, 1080.00], "ABRAZADERAS PERFECTO - Standard Fleje 9mm", "PROV", "hoja1")
for item in ext: print(item['codigo_proveedor'], "|", item['descripcion'], "|", item['costo_neto'])
# Expected: "98-1045 | ABRAZADERAS PERFECTO - Standard Fleje 9mm - 30- 45 | 1080.00"

# 4. Code duplicating description text entirely
_, ext2 = app._process_heuristic_row(["300010      Trabasil RA3 50g", 2500.50], "SELLADORES", "PROV", "hoja1")
for item in ext2: print(item['codigo_proveedor'], "|", item['descripcion'], "|", item['costo_neto'])
# Expected: "300010 | SELLADORES - Trabasil RA3 50g | 2500.50" (Orphan prepends context, Code separated from description)
