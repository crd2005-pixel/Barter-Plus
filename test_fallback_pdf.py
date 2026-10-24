from unificador_listas.app import App
import pandas as pd
import numpy as np

app = App()

df = pd.DataFrame({
    0: ['ABRAZADERAS', '14"', '5800', '175/70-13'],
    1: [np.nan, '$3,900.00', '$3,850.00', '175/65-14 155/70-15 190/55-365'],
    2: [np.nan, np.nan, np.nan, '$35,600.00']
})

app.api_key = "dummy"

import pdfplumber

# Try fallback logic explicitly
class MockPage:
    def extract_text(self, **kwargs):
        return "CODIGO1 $ 100.00\nCODIGO2 200.00\nCODIGO3 $ 300.00"
    def extract_tables(self):
        return []

page = MockPage()

# The code currently handles fallback lines inside the LLM _extract_data_from_blocks
# We want to ensure that if LLM is disabled or fails, the heuristic line-by-line fallback works.

text = page.extract_text(vertical_strategy="lines")
if text:
    lines = text.split('\n')
    data = []
    for line in lines:
        data.append([p.strip() for p in line.split('  ') if p.strip()])
    df_lines = pd.DataFrame(data)
    app._fallback_heuristic_parse(df_lines, "Pag 1 Lineas", "PROV")

for i in app.extracted_data:
    print(i['codigo_proveedor'], i['costo_neto'])
