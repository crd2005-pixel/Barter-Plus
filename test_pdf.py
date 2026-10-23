import re
import math
import pdfplumber
import traceback

def limpiar_importe_ar(valor_str):
    if not isinstance(valor_str, str):
        return 0.0
    s = re.sub(r'[^\d.,]', '', valor_str.strip())
    if not s: return 0.0

    if '.' in s and ',' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    elif '.' in s:
        partes = s.split('.')
        if len(partes) > 1 and len(partes[-1]) == 3:
            s = s.replace('.', '')

    try:
        val = round(float(s), 2)
        return val if val > 0 else 0.0
    except ValueError:
        return 0.0

def extraer_productos_de_pdf(ruta_pdf: str, proveedor: str) -> list:
    extracted = []
    PATRON_MEMBRETE = re.compile(
        r'(tel\s*[:.]?|cel\s*[:.]?|fax|0260|0261|44\d[\s-]?\d{3}|sarmiento|san\s+rafael|mendoza|cuit|iva\s|www\.|http|@|distribuidora|hoja\s*\d|p[aá]gina|c[óo]digo|descripci[óo]n|lista|vigencia|descuento)',
        re.IGNORECASE
    )

    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for i, page in enumerate(pdf.pages):
                seccion_actual = f"Pag {i+1}"
                tables = page.extract_tables()
                page_items = 0

                if tables:
                    for table in tables:
                        for row in table:
                            if not any(row): continue

                            # Header detection
                            text_cells = [str(c).strip() for c in row if c and str(c).strip() and '$' not in str(c)]
                            precio_cells = [str(c).strip() for c in row if c and '$' in str(c)]

                            if not precio_cells and len(text_cells) in [1, 2]:
                                val = text_cells[0]
                                if not PATRON_MEMBRETE.search(val):
                                    seccion_actual = re.sub(r'\d+\s*PRODUCTOS?', '', val, flags=re.IGNORECASE).strip()
                                continue

                            precio_col_idx = -1
                            precios_encontrados = []
                            for idx_c, cell in enumerate(row):
                                if not cell: continue
                                val = str(cell).strip()
                                if '$' in val:
                                    prices = re.findall(r'\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?', val)
                                    if prices:
                                        precio_col_idx = idx_c
                                        precios_encontrados = prices

                            if precio_col_idx == -1: continue

                            codigo_col_idx = -1
                            codigos_linea = []
                            for idx_c, cell in enumerate(row):
                                val = str(cell).strip() if cell else ""
                                if val:
                                    codigo_col_idx = idx_c
                                    codigos_linea = [c for c in val.split('\n') if c.strip()]
                                    break

                            if codigo_col_idx == -1 or codigo_col_idx == precio_col_idx: continue

                            # Multi-Line Rule
                            if len(codigos_linea) > 1 and len(precios_encontrados) == len(codigos_linea):
                                amp_col = codigo_col_idx + 1 if precio_col_idx > codigo_col_idx + 1 else -1
                                marca_col = codigo_col_idx + 2 if precio_col_idx > codigo_col_idx + 2 else -1
                                aplic_col = codigo_col_idx + 3 if precio_col_idx > codigo_col_idx + 3 else -1

                                amps_vals = str(row[amp_col]).strip().split('\n') if amp_col != -1 and row[amp_col] else []
                                amps_vals = [x for x in amps_vals if x.strip()]

                                marca_str = str(row[marca_col]).strip() if marca_col != -1 and row[marca_col] else ""
                                lines = marca_str.split('\n')
                                marcas_limpias = lines if len(lines) == len(codigos_linea) else [" ".join(lines)] * len(codigos_linea)

                                aplic_str = str(row[aplic_col]).strip().replace('\n', ' ') if aplic_col != -1 and row[aplic_col] else ""

                                for j in range(len(codigos_linea)):
                                    amp = amps_vals[j] if j < len(amps_vals) else ""
                                    marca = marcas_limpias[j] if j < len(marcas_limpias) else (marcas_limpias[0] if marcas_limpias else "GENERICA")
                                    desc = f"{seccion_actual} - {amp} - {marca} - {aplic_str}".strip(" -")
                                    desc = re.sub(r'\s{2,}', ' ', desc)
                                    extracted.append({
                                        'proveedor': proveedor,
                                        'codigo_proveedor': codigos_linea[j],
                                        'descripcion': desc,
                                        'marca': marca,
                                        'costo_neto': limpiar_importe_ar(precios_encontrados[j]),
                                        'origen': f"Pag {i+1}"
                                    })
                                    page_items += 1

                            # Rule B Single product
                            elif len(codigos_linea) == 1:
                                cod = codigos_linea[0]
                                precio_val = str(row[precio_col_idx]).strip()

                                eq_pre_price = []
                                if '\n' in precio_val:
                                    parts = precio_val.split('\n')
                                    for p in parts:
                                        if '$' in p: precio_val = p
                                        else: eq_pre_price.append(p)

                                desc_parts = []
                                for j in range(codigo_col_idx + 1, precio_col_idx):
                                    val = str(row[j]).strip()
                                    if not val: continue
                                    if val.isdigit() and len(val) <= 3: continue
                                    desc_parts.append(val)

                                desc = f"{seccion_actual} - {' '.join(desc_parts)}".strip(" -")

                                equivalences = eq_pre_price
                                for j in range(precio_col_idx + 1, len(row)):
                                    val = str(row[j]).strip()
                                    if val and '$' not in val: equivalences.append(val)

                                if equivalences:
                                    desc += f" [Eq: {' / '.join(equivalences)}]"

                                extracted.append({
                                    'proveedor': proveedor,
                                    'codigo_proveedor': cod,
                                    'descripcion': desc,
                                    'marca': "GENERICA",
                                    'costo_neto': limpiar_importe_ar(precios_encontrados[0]),
                                    'origen': f"Pag {i+1}"
                                })
                                page_items += 1

                if page_items == 0:
                    text = page.extract_text(layout=True)
                    if text:
                        for line in text.split('\n'):
                            if '$' in line:
                                parts = [p.strip() for p in line.split() if p.strip()]
                                if len(parts) >= 2:
                                    prices = re.findall(r'\$\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?', line)
                                    if prices:
                                        cod = parts[0]
                                        costo = limpiar_importe_ar(prices[-1])
                                        if costo > 0:
                                            desc = line.replace(cod, '', 1).replace(prices[-1], '').strip()
                                            desc = f"{seccion_actual} - {desc}".strip(" -")
                                            extracted.append({
                                                'proveedor': proveedor,
                                                'codigo_proveedor': cod,
                                                'descripcion': desc,
                                                'marca': "GENERICA",
                                                'costo_neto': costo,
                                                'origen': f"Pag {i+1} Lineas"
                                            })
    except Exception as e:
        print("Extract exception:", traceback.format_exc())
    return extracted
