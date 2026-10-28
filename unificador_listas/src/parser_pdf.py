import pdfplumber
import re

def parse_pdf_deterministic(pdf_path, config=None):
    """
    Motor Determinista Especializado para PDF.
    Resuelve los casos de:
    - Seineca (precio en el medio, equivalencias a la derecha).
    - La Casa de las Baterías (celdas multilíneas agrupadas).
    """
    productos_extraidos = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table: continue

                # Check for "La Casa de las Baterías" style grouping (multiline cells)
                if _is_baterias_format(table):
                    productos_extraidos.extend(_parse_baterias_table(table, config))
                elif _is_seineca_format(table):
                    productos_extraidos.extend(_parse_seineca_table(table))
                else:
                    # Generic table parsing
                    productos_extraidos.extend(_parse_generic_table(table))

    return productos_extraidos

def limpiar_precio(precio_str):
    if not precio_str: return 0.0
    s = re.sub(r'[^\d.,]', '', str(precio_str).strip())
    if not s: return 0.0

    # Manejar formatos argentinos
    if '.' in s and ',' in s:
        if s.rfind(',') > s.rfind('.'): # Ej: 1.500,50
            s = s.replace('.', '').replace(',', '.')
        else: # Ej: 1,500.50
            s = s.replace(',', '')
    elif ',' in s: # Ej: 1500,50
        s = s.replace(',', '.')
    elif '.' in s: # Ej: 1.500 o 1500.50
        partes = s.split('.')
        if len(partes) > 1 and len(partes[-1]) == 3:
            s = s.replace('.', '')
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0

def _is_baterias_format(table):
    # Detects if a table row has multiline strings that suggest grouped batteries
    if not table: return False
    for row in table[:3]:
        if not row: continue
        for cell in row:
            if isinstance(cell, str) and cell.count('\n') >= 2:
                # Si una celda tiene muchos saltos, es probable formato batería
                if "AMP. COMERCIAL" in str(row) or "LARGO" in str(row) or "ANCHO" in str(row):
                    return True
    return False

def _parse_baterias_table(table, config):
    productos = []
    # config: {"baterias_precio_col": "FINAL C/USADA" o "COSTO S/USADA"}
    precio_col_idx = 9 # Default: FINAL C/USADA (col 9)
    # asumiendo estructura: CÓDIGO (0) | AMP. COMERCIAL (1) | MARCA (2) | PRINCIPAL APLICACIÓN (3) | LARGO (4) | ANCHO (5) | ALTO (6) | COSTO S/USADA (7) | VALOR USADA (8) | FINAL C/USADA (9)
    if config and config.get("baterias_precio_col") == "COSTO S/USADA":
        precio_col_idx = 7

    for row in table:
        if not row or len(row) < 4: continue

        # Omitir cabecera
        if "CÓDIGO" in str(row[0]).upper():
            continue

        codigos = str(row[0]).split('\n')
        amps = str(row[1]).split('\n') if len(row) > 1 and row[1] else []
        marcas_raw = str(row[2]).split('\n') if len(row) > 2 and row[2] else []

        # Reconstruir marcas partidas
        marcas = []
        temp_marca = ""
        for m in marcas_raw:
            if m.strip() == "STOP":
                if marcas: marcas[-1] += " " + m.strip()
                continue
            if temp_marca:
                marcas.append(temp_marca)
            temp_marca = m.strip()
        if temp_marca: marcas.append(temp_marca)

        # Aplicación compartida
        aplicacion = str(row[3]).replace('\n', ' ') if len(row) > 3 and row[3] else ""

        # Precios
        precios_raw = str(row[precio_col_idx]).split('\n') if len(row) > precio_col_idx and row[precio_col_idx] else []
        precios = [p.strip() for p in precios_raw if p.strip() and p.strip() != '$']

        # Alinear
        max_len = max(len(codigos), len(precios))
        for i in range(max_len):
            cod = codigos[i].strip() if i < len(codigos) else ""
            if not cod or cod == '$' or cod.replace('.', '').replace(',', '').isdigit():
                continue # PROHIBIDO que codigo_proveedor sea $ o numérico de precio

            marca = marcas[i] if i < len(marcas) else (marcas[-1] if marcas else "")
            amp = amps[i] if i < len(amps) else ""
            precio_str = precios[i] if i < len(precios) else "0"
            costo = limpiar_precio(precio_str)

            if costo > 0:
                productos.append({
                    "codigo_proveedor": cod,
                    "descripcion": f"{amp} - {aplicacion}".strip(" -"),
                    "marca": marca,
                    "costo": costo
                })

    return productos

def _is_seineca_format(table):
    if not table: return False
    # Detect if table has CÓDIGO (0) | DESCRIPCIÓN (1) | PRECIO (2) | MANN (3) | FRAM (4) | WEGA (5) | MARENO (6)
    for row in table[:3]:
        if not row: continue
        row_str = " ".join([str(c) for c in row]).upper()
        if "MANN" in row_str and "FRAM" in row_str and "WEGA" in row_str:
            return True
    return False

def _parse_seineca_table(table):
    productos = []
    seccion_actual = "FILTROS"

    for row in table:
        if not row: continue

        # Check if it's a section title (only col 1 filled)
        if (row[0] is None or str(row[0]).strip() == "") and len(row) > 1 and row[1]:
            txt = str(row[1]).strip().upper()
            if "FILTROS DE" in txt:
                seccion_actual = txt
                continue

        # Header skip
        if row[0] and "CÓDIGO" in str(row[0]).upper():
            continue

        cod = str(row[0]).strip() if row[0] else ""
        precio_str = str(row[2]).strip() if len(row) > 2 and row[2] else ""

        # Falla 3: Handle the case where pdfplumber joins CODE and PRICE with \n
        if '\n' in cod:
            partes = cod.split('\n')
            cod = partes[0]
            # Si hay un signo $ en la segunda parte, usarlo como precio
            if len(partes) > 1 and '$' in partes[1]:
                precio_str = partes[1]

        if not cod: continue

        desc = str(row[1]).strip() if len(row) > 1 and row[1] else ""

        # Append section and equivalences
        equivalencias = []
        if len(row) > 3 and row[3]: equivalencias.append(f"MANN: {str(row[3]).strip()}")
        if len(row) > 4 and row[4]: equivalencias.append(f"FRAM: {str(row[4]).strip()}")
        if len(row) > 5 and row[5]: equivalencias.append(f"WEGA: {str(row[5]).strip()}")
        if len(row) > 6 and row[6]: equivalencias.append(f"MARENO: {str(row[6]).strip()}")

        eq_str = " | ".join([e for e in equivalencias if e and e.split(":")[1].strip() != "-"])

        final_desc = desc
        if seccion_actual:
            final_desc += f" - {seccion_actual}"
        if eq_str:
            final_desc += f" [Eq: {eq_str}]"

        costo = limpiar_precio(precio_str)

        # Candado: PROHIBIDO que codigo_proveedor sea $ o numérico (si es menor a 4 digitos y parece precio)
        if cod == '$' or (cod.replace('.','').replace(',','').isdigit() and len(cod) < 5 and '.' in cod):
            continue

        # Regla 3: El costo debe ser estricatemente mayor a 0
        if costo > 0:
            productos.append({
                "codigo_proveedor": cod.replace('$', '').strip(),
                "descripcion": final_desc.replace('\n', ' '),
                "marca": "SEINECA", # Default by file type
                "costo": costo
            })

    return productos

def _parse_generic_table(table):
    productos = []
    for row in table:
        if not row: continue
        # Basic parsing logic for generic tables...
        # Just an example implementation, real generic logic would be more robust
        clean_row = [str(c).strip() for c in row if c]
        if len(clean_row) >= 3:
            cod = clean_row[0]
            desc = clean_row[1]
            precio_str = clean_row[-1]
            if '$' in cod or cod.replace('.', '').replace(',', '').isdigit() and len(cod)<4:
                continue
            costo = limpiar_precio(precio_str)
            if costo > 0:
                productos.append({
                    "codigo_proveedor": cod,
                    "descripcion": desc.replace('\n', ' '),
                    "marca": "GENERICA",
                    "costo": costo
                })
    return productos
