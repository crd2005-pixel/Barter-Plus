import re

with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update `extraer_productos_de_pdf` to call the fallback if result is empty or exception occurs
new_extract_pdf = """
def extraer_productos_de_pdf(ruta_pdf: str, proveedor: str, api_key: str) -> list:
    extracted_total = []

    try:
        with open(ruta_pdf, 'rb') as f:
            pdf_bytes = f.read()

        extracted_list = extraer_productos_dinamico_multimodal(ruta_pdf, proveedor, api_key, 'pdf', page_num=0, pdf_bytes=pdf_bytes)

        for prod in extracted_list:
            cod = str(prod['codigo_proveedor']).strip()
            desc = str(prod['descripcion']).strip()
            costo = prod['costo_neto']

            if '$' in cod or re.match(r'^\\$?\\s*\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?$', cod):
                continue

            if not desc or desc.startswith("Pag ") and "$" in desc:
                if len(re.sub(r'Pag\\s*\\d+\\s*-\\s*\\$\\s*[\\d.,]+', '', desc).strip()) == 0:
                     continue
            if re.match(r'^\\$?\\s*\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2})?$', desc):
                continue

            extracted_total.append(prod)

    except Exception as e:
        import traceback
        with open('unificador_listas/error_log.txt', 'a', encoding='utf-8') as flog:
            flog.write(f"Error multimodal pdf: {e}\\n{traceback.format_exc()}\\n")

    # CRITICAL: Always fallback if empty
    if not extracted_total:
        extracted_total = _fallback_pdf_determinista(ruta_pdf, proveedor)

    return extracted_total
"""

# Update `extraer_productos_dinamico_multimodal` to properly parse markdown json and arrays
new_multimodal_dynamic = """
def extraer_productos_dinamico_multimodal(ruta_archivo: str, proveedor: str, api_key: str, tipo_archivo: str, page_num: int = None, pdf_bytes: bytes = None) -> list:
    if not genai or not api_key:
        return []

    client = genai.Client(api_key=api_key)

    class ProductoExtraido(BaseModel):
        codigo_proveedor: str = Field(description="El código real del artículo. PROHIBIDO que empiece con '$' o sea un importe.")
        descripcion: str = Field(description="Nombre completo, tipo de producto, medidas, aplicación. PROHIBIDO incluir direcciones, teléfonos, o precios.")
        marca: str = Field(description="La marca real del artículo detectada en la fila, columna o sección.")
        costo: float = Field(description="El precio unitario final numérico puro (tomar el precio final y omitir valores parciales o entregas de cascos).")

    class ListaProductos(BaseModel):
        productos: List[ProductoExtraido]

    prompt_texto = f\"\"\"
    Eres un extractor determinista de listas de precios para el proveedor '{proveedor}'.
    Extrae estrictamente los productos de la imagen o documento adjunto.

    REGLAS ESTRICTAS:
    1. Si una celda o fila agrupa varios códigos apilados verticalmente con sus respectivos amperajes, marcas y precios (como en listas de baterías), desglosa cada código como un producto individual alineando su marca, amperaje, aplicación compartida y su precio correspondiente.
    2. Si una tabla tiene el precio en una columna central y códigos de equivalencia (MANN, FRAM, WEGA, MARENO) a la derecha, toma el precio de la columna Precio e incluye las equivalencias dentro de la descripción.
    3. Ignora membretes comerciales, teléfonos, direcciones, descuentos generales de cabecera y números de página.
    4. Jamás permitas que un código de proveedor contenga el símbolo "$" o parezca un precio.
    5. Jamás permitas que la descripción contenga valores monetarios aislados sin contexto.
    \"\"\"

    try:
        if tipo_archivo == 'pdf' and pdf_bytes:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    genai.types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    prompt_texto
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ListaProductos
                )
            )
        elif tipo_archivo == 'excel' and pdf_bytes:
             response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    pdf_bytes,
                    prompt_texto
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ListaProductos
                )
            )
        else:
            return []

        text_resp = response.text

        # Clean markdown
        if text_resp.startswith("```json"):
            text_resp = text_resp.strip()[7:-3]
        elif text_resp.startswith("```"):
            text_resp = text_resp.strip()[3:-3]

        data = json.loads(text_resp)

        # Unpack if nested in dict
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list):
                    items_list = v
                    break
            else:
                items_list = [data] # Fallback
        elif isinstance(data, list):
            items_list = data
        else:
            items_list = []

        extracted = []
        origen = f"Pag {page_num+1}" if page_num is not None else "Documento"

        for item in items_list:
            cod = item.get('codigo_proveedor') or item.get('codigo') or ''
            desc = item.get('descripcion') or item.get('desc') or ''
            marca = item.get('marca', 'GENERICA')
            cost = item.get('costo') or item.get('precio') or item.get('costo_neto') or 0.0

            extracted.append({
                'proveedor': proveedor,
                'codigo_proveedor': cod,
                'descripcion': desc,
                'marca': marca,
                'costo_neto': float(cost) if cost else 0.0,
                'origen': origen
            })

        return extracted
    except Exception as e:
        import traceback
        with open('unificador_listas/error_log.txt', 'a', encoding='utf-8') as flog:
            flog.write(f"Error multimodal json: {e}\\n{traceback.format_exc()}\\n")
        return []
"""

# Replace the functions in app.py
start_pdf_idx = content.find("def extraer_productos_de_pdf")
end_pdf_idx = content.find("def _fallback_pdf_determinista")

if start_pdf_idx != -1 and end_pdf_idx != -1:
    content = content[:start_pdf_idx] + new_extract_pdf + "\n" + content[end_pdf_idx:]

start_multi_idx = content.find("def extraer_productos_dinamico_multimodal")
end_multi_idx = content.find("def extraer_productos_de_pdf")

if start_multi_idx != -1 and end_multi_idx != -1:
    content = content[:start_multi_idx] + new_multimodal_dynamic + "\n" + content[end_multi_idx:]

with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated multimodal parsing and fallback routing.")
