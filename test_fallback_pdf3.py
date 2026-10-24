from unificador_listas.app import App
import pdfplumber

class MockPage:
    def extract_tables(self):
        return []
    def extract_text(self, layout=False):
        return "CODIGO1 $ 100.00\nCODIGO2 200.00\nSolo texto sin precio"

page = MockPage()
text = page.extract_text(layout=True)

data = []
import re
lines = text.split('\n')
for line in lines:
    if ' $' in line:
        parts = line.split(' $')
        parts[1] = '$' + parts[1]
    else:
        parts = [p.strip() for p in line.split('  ') if p.strip()]
        if not parts: parts = line.split()

    clean_parts = [p.strip() for p in parts if p.strip()]
    if len(clean_parts) >= 2 and any('$' in p or re.search(r'\d', p) for p in clean_parts):
        data.append(clean_parts)

print(data)
