with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

fallback_code = """
def _fallback_pdf_determinista(ruta_pdf: str, proveedor: str) -> list:
    extracted_total = []

    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for page_num, page in enumerate(pdf.pages):
                seccion_actual = f"Pag {page_num+1}"
                tables = page.extract_tables()

                if tables:
                    for table in tables:
                        for row in table:
                            extracted, seccion_actual = _process_table_row(row, proveedor, seccion_actual, page_num)
                            if extracted:
                                extracted_total.extend(extracted)

    except Exception as e:
        import traceback
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'error_log.txt'), 'a', encoding='utf-8') as flog:
            flog.write(f"Error _fallback_pdf_determinista: {e}\\n{traceback.format_exc()}\\n")

    return extracted_total

def _process_table_row(row, proveedor, seccion_actual, page_num):
    extracted = []

    celdas = [str(c).strip() if c is not None else "" for c in row]
    if not any(celdas): return extracted, seccion_actual

    if celdas[0]:
        first_cell_upper = celdas[0].upper()
        if any(first_cell_upper.startswith(x) for x in ["CÓDIGO", "CODIGO", "DESCRIPCIÓN", "DESCRIPCION", "LISTA", "VIGENCIA", "TEL", "E-MAIL", "DESCUENTO"]):
            return extracted, seccion_actual

    # Section check
    has_dollar = any('$' in c for c in celdas)
    has_amount = any(re.search(r'\\d{1,3}\\.\\d{3}', c) for c in celdas)

    if not has_dollar and not has_amount and len([c for c in celdas if c]) in [1, 2]:
        text_val = [c for c in celdas if c][0]
        if not re.search(r'(tel\\s*[:.]?|cel\\s*[:.]?|fax|cuit|iva\\s|www\\.|http|@)', text_val, re.IGNORECASE):
            seccion_actual = re.sub(r'\\d+\\s*PRODUCTOS?', '', text_val, flags=re.IGNORECASE).strip()
            return extracted, seccion_actual

    cols_precio = []
    for i, c in enumerate(celdas):
        if '$' in c or re.search(r'\\$\\s*\\d{1,3}(?:\\.\\d{3})+', c):
            cols_precio.append(i)

    if not cols_precio:
        return extracted, seccion_actual

    # RULE 1: Code from Col 0
    codigo_raw = celdas[0]
    if '$' in codigo_raw:
        return extracted, seccion_actual

    # RULE 2: Multi-line Grouped
    if '\\n' in codigo_raw:
        codigos = [c.strip() for c in codigo_raw.split('\\n') if c.strip() and '$' not in c]
        precios_str = celdas[cols_precio[-1]]
        precios = re.findall(r'\\d{1,3}(?:\\.\\d{3})+(?:,\\d{1,2})?', precios_str)

        if len(codigos) >= 1 and len(precios) == len(codigos):
            amp_col = celdas[1].split('\\n') if len(celdas) > 1 else []
            amp_col = [x.strip() for x in amp_col if x.strip()]

            marca_col = celdas[2].split('\\n') if len(celdas) > 2 else []
            marca_col = [x.strip() for x in marca_col if x.strip()]

            aplic = celdas[3].replace('\\n', ' ').strip() if len(celdas) > 3 else ""

            for i in range(len(codigos)):
                amp = amp_col[i] if i < len(amp_col) else (amp_col[0] if amp_col else "")
                marca = marca_col[i] if i < len(marca_col) else (marca_col[0] if marca_col else "GENERICA")

                desc = f"{seccion_actual} - {amp} - {aplic}".strip(" -")
                desc = re.sub(r'\\s{2,}', ' ', desc)

                extracted.append({
                    'proveedor': proveedor,
                    'codigo_proveedor': codigos[i],
                    'descripcion': desc,
                    'marca': marca,
                    'costo_neto': limpiar_importe_ar(precios[i]),
                    'origen': f"Pag {page_num+1}"
                })
            return extracted, seccion_actual

    # RULE 3: Central Price + Equivalences
    if len(cols_precio) == 1:
        idx_p = cols_precio[0]
        codigo_proveedor = celdas[0].replace('\\n', ' ').strip()

        match_price = re.search(r'\\$\\s*(\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{1,2})?)', celdas[idx_p])
        costo = limpiar_importe_ar(match_price.group(1)) if match_price else 0.0

        if costo > 0:
            eqs = []
            celda_precio_parts = celdas[idx_p].split('\\n')
            for part in celda_precio_parts:
                if part.strip() and '$' not in part:
                    eqs.append(part.strip())

            for i in range(idx_p + 1, len(celdas)):
                if celdas[i]:
                    eqs.append(celdas[i].replace('\\n', ' ').strip())

            desc = f"{seccion_actual} - {celdas[1].replace(chr(10), ' ').strip()}"
            if eqs:
                desc += f" [Eq: {' / '.join(eqs)}]"

            extracted.append({
                'proveedor': proveedor,
                'codigo_proveedor': codigo_proveedor,
                'descripcion': desc,
                'marca': "GENERICA",
                'costo_neto': costo,
                'origen': f"Pag {page_num+1}"
            })

    return extracted, seccion_actual
"""

# Inject before class App
app_idx = content.find("class App(ctk.CTk):")
if app_idx != -1:
    new_content = content[:app_idx] + fallback_code + "\n" + content[app_idx:]
    with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Injected fallback methods.")
else:
    print("Could not find App class.")
