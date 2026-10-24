import re
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

def process_table_row(row, proveedor, seccion_actual):
    extracted = []

    celdas = [str(c).strip() if c is not None else "" for c in row]
    if not any(celdas): return extracted, seccion_actual

    if celdas[0]:
        first_cell_upper = celdas[0].upper()
        if any(first_cell_upper.startswith(x) for x in ["CÓDIGO", "CODIGO", "DESCRIPCIÓN", "DESCRIPCION", "LISTA", "VIGENCIA", "TEL", "E-MAIL", "DESCUENTO"]):
            return extracted, seccion_actual

    # Section check
    has_dollar = any('$' in c for c in celdas)
    has_amount = any(re.search(r'\d{1,3}\.\d{3}', c) for c in celdas)

    if not has_dollar and not has_amount and len([c for c in celdas if c]) in [1, 2]:
        text_val = [c for c in celdas if c][0]
        if not re.search(r'(tel\s*[:.]?|cel\s*[:.]?|fax|cuit|iva\s|www\.|http|@)', text_val, re.IGNORECASE):
            seccion_actual = re.sub(r'\d+\s*PRODUCTOS?', '', text_val, flags=re.IGNORECASE).strip()
            return extracted, seccion_actual

    cols_precio = []
    for i, c in enumerate(celdas):
        if '$' in c or re.search(r'\$\s*\d{1,3}(?:\.\d{3})+', c):
            cols_precio.append(i)

    if not cols_precio:
        return extracted, seccion_actual

    # RULE 1: Code from Col 0
    codigo_raw = celdas[0]
    if '$' in codigo_raw:
        return extracted, seccion_actual

    # RULE 2: Multi-line Grouped
    if '\n' in codigo_raw:
        codigos = [c.strip() for c in codigo_raw.split('\n') if c.strip() and '$' not in c]
        precios_str = celdas[cols_precio[-1]]
        precios = re.findall(r'\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?', precios_str)

        if len(codigos) >= 1 and len(precios) == len(codigos):
            amp_col = celdas[1].split('\n') if len(celdas) > 1 else []
            amp_col = [x.strip() for x in amp_col if x.strip()]

            marca_col = celdas[2].split('\n') if len(celdas) > 2 else []
            marca_col = [x.strip() for x in marca_col if x.strip()]

            aplic = celdas[3].replace('\n', ' ').strip() if len(celdas) > 3 else ""

            for i in range(len(codigos)):
                amp = amp_col[i] if i < len(amp_col) else (amp_col[0] if amp_col else "")
                marca = marca_col[i] if i < len(marca_col) else (marca_col[0] if marca_col else "GENERICA")

                desc = f"{seccion_actual} - {amp} - {aplic}".strip(" -")
                desc = re.sub(r'\s{2,}', ' ', desc)

                extracted.append({
                    'proveedor': proveedor,
                    'codigo_proveedor': codigos[i],
                    'descripcion': desc,
                    'marca': marca,
                    'costo_neto': limpiar_importe_ar(precios[i]),
                    'origen': "Fallback"
                })
            return extracted, seccion_actual

    # RULE 3: Central Price + Equivalences
    if len(cols_precio) == 1:
        idx_p = cols_precio[0]
        codigo_proveedor = celdas[0].replace('\n', ' ').strip()

        match_price = re.search(r'\$\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)', celdas[idx_p])
        costo = limpiar_importe_ar(match_price.group(1)) if match_price else 0.0

        if costo > 0:
            eqs = []
            celda_precio_parts = celdas[idx_p].split('\n')
            for part in celda_precio_parts:
                if part.strip() and '$' not in part:
                    eqs.append(part.strip())

            for i in range(idx_p + 1, len(celdas)):
                if celdas[i]:
                    eqs.append(celdas[i].replace('\n', ' ').strip())

            desc = f"{seccion_actual} - {celdas[1].replace(chr(10), ' ').strip()}"
            if eqs:
                desc += f" [Eq: {' / '.join(eqs)}]"

            extracted.append({
                'proveedor': proveedor,
                'codigo_proveedor': codigo_proveedor,
                'descripcion': desc,
                'marca': "GENERICA", # Can be extracted differently if Seineca
                'costo_neto': costo,
                'origen': "Fallback"
            })

    return extracted, seccion_actual

def test():
    # Test La Casa de las Baterias
    row_baterias = [
        "M22ED\nLP 670\nDL 620\nBP 620 (6meses)\nUB 620",
        "12X65\n12X65\n12X65\n12X65\n12X65",
        "WILLARD\nMOURA\nLEMOM\nPREMIUM\nSEINECA",
        "ford k fiesta - ecosport - agile - fiorino",
        "$\n$ 113.873\n$ 71.187\n$ 60.500\n$ 55.000\n$ 45.000"
    ]
    extracted, _ = process_table_row(row_baterias, "BAT", "BATERIAS")
    print(extracted)
    assert len(extracted) == 5
    assert extracted[0]['codigo_proveedor'] == 'M22ED'
    assert extracted[0]['marca'] == 'WILLARD'
    assert extracted[0]['costo_neto'] == 113873.0

    # Test Seineca
    row_seineca = [
        "SFF32205",
        "AA1482/1 E F. AIRE VW AMAROK",
        "WK6002\n$ 12.272",
        "MANN1",
        "FRAM1",
        "",
        "MARENO1"
    ]
    extracted, _ = process_table_row(row_seineca, "SEINECA", "FILTROS")
    print(extracted)
    assert len(extracted) == 1
    assert extracted[0]['codigo_proveedor'] == 'SFF32205'
    assert extracted[0]['costo_neto'] == 12272.0
    assert "WK6002" in extracted[0]['descripcion']
    assert "MANN1" in extracted[0]['descripcion']

    print("All tests passed!")

if __name__ == "__main__":
    test()
