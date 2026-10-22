from unificador_listas.app import App
import pandas as pd
import numpy as np

app = App()

# Fila 8: 2 textos: "ABRAZADERAS PERFECTO", "ACEITES SUELTOS" (no se detectó como título en el código antiguo)
# Si es una isla/segmento, "ABRAZADERAS PERFECTO" y "ACEITES SUELTOS" deben ser títulos separados.
row = ["ABRAZADERAS PERFECTO", np.nan, "ACEITES SUELTOS"]

# In the current logic:
print("Segs:", app._extract_segments_from_row(row))
# [ ['ABRAZADERAS PERFECTO'], ['ACEITES SUELTOS'] ]
