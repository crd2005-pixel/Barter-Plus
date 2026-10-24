import re

with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the new multimodal extraction functions
multimodal_functions = """
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
        elif tipo_archivo == 'excel' and pdf_bytes: # Re-using bytes variable for text in excel
             response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    pdf_bytes, # Treat as text block for excel fallback
                    prompt_texto
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ListaProductos
                )
            )
        else:
            return []

        data = json.loads(response.text)

        extracted = []
        origen = f"Pag {page_num+1}" if page_num is not None else "Documento"

        for item in data.get('productos', []):
            extracted.append({
                'proveedor': proveedor,
                'codigo_proveedor': item.get('codigo_proveedor', ''),
                'descripcion': item.get('descripcion', ''),
                'marca': item.get('marca', 'GENERICA'),
                'costo_neto': item.get('costo', 0.0),
                'origen': origen
            })

        return extracted
    except Exception as e:
        import traceback
        print("Error multimodal:", traceback.format_exc())
        return []

def extraer_productos_de_pdf(ruta_pdf: str, proveedor: str, api_key: str) -> list:
    extracted_total = []

    try:
        import fitz # PyMuPDF for efficient page by page bytes extraction if needed, but we'll use open read
        with open(ruta_pdf, 'rb') as f:
            pdf_bytes = f.read()

        # Send entire PDF (up to limits) or split. For now send whole PDF if small enough, or iterate.
        # GenAI Flash supports large contexts, sending the whole PDF binary is acceptable for many cases.
        # But we were instructed to divide or process in blocks of 1-2 pages or send binary.
        # Let's send the binary directly as requested: `types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")`

        extracted_list = extraer_productos_dinamico_multimodal(ruta_pdf, proveedor, api_key, 'pdf', page_num=0, pdf_bytes=pdf_bytes)

        # Validation Candado Determinista (post-extraction)
        for prod in extracted_list:
            cod = str(prod['codigo_proveedor']).strip()
            desc = str(prod['descripcion']).strip()
            costo = prod['costo_neto']

            # Reject if code has $ or matches a price format
            if '$' in cod or re.match(r'^\$?\s*\d{1,3}(?:\.\d{3})+(?:,\d{2})?$', cod):
                continue

            # Reject if description is just a price or empty
            if not desc or desc.startswith("Pag ") and "$" in desc:
                # Basic check, we can refine
                if len(re.sub(r'Pag\s*\d+\s*-\s*\$\s*[\d.,]+', '', desc).strip()) == 0:
                     continue
            if re.match(r'^\$?\s*\d{1,3}(?:\.\d{3})+(?:,\d{2})?$', desc):
                continue

            # Valid product
            extracted_total.append(prod)

    except Exception as e:
        print(f"Error procesando PDF: {e}")

    return extracted_total

"""

# We need to replace the old `extraer_productos_de_pdf` and `limpiar_importe_ar` block with the new one.
# Find the start of `def limpiar_importe_ar` and end of `def extraer_productos_de_pdf`

start_idx = content.find("def limpiar_importe_ar")
if start_idx != -1:
    end_str = "print(\"Extract exception:\", traceback.format_exc())\n    return extracted"
    end_idx = content.find(end_str, start_idx)

    if end_idx != -1:
        end_idx += len(end_str)
        # We replace this section
        new_content = content[:start_idx] + multimodal_functions + content[end_idx:]

        # Also need to update `process_file` to pass `self.api_key` to `extraer_productos_de_pdf`
        process_file_idx = new_content.find("extracted_list = extraer_productos_de_pdf(self.current_file, proveedor)")
        if process_file_idx != -1:
             new_content = new_content.replace(
                "extracted_list = extraer_productos_de_pdf(self.current_file, proveedor)",
                "extracted_list = extraer_productos_de_pdf(self.current_file, proveedor, self.api_key)"
             )

        with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Replaced PDF extraction logic.")
    else:
        print("Could not find end of PDF extraction logic.")
else:
    print("Could not find start of PDF extraction logic.")
