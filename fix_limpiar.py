with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add `limpiar_importe_ar` method
limpiar_code = """
def limpiar_importe_ar(valor_str):
    if not isinstance(valor_str, str):
        return 0.0
    import re
    s = re.sub(r'[^\\d.,]', '', valor_str.strip())
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
"""

app_idx = content.find("def _fallback_pdf_determinista")
if app_idx != -1:
    new_content = content[:app_idx] + limpiar_code + "\n" + content[app_idx:]
    with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Injected limpiar_importe_ar.")
else:
    print("Could not find insertion point.")
