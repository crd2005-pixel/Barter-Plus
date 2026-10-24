import re

with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Let's ensure `registrar_error_seguro` is correctly used in `extraer_productos_de_pdf` and `extraer_productos_dinamico_multimodal`
new_pdf_extract = """
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
        registrar_error_seguro(f"Error multimodal pdf: {e}\\n{traceback.format_exc()}")

    # CRITICAL: Always fallback if empty
    if not extracted_total:
        extracted_total = _fallback_pdf_determinista(ruta_pdf, proveedor)

    return extracted_total
"""

start_idx = content.find("def extraer_productos_de_pdf")
end_idx = content.find("def extraer_productos_dinamico_multimodal")
if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_pdf_extract + "\n" + content[end_idx:]

with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
