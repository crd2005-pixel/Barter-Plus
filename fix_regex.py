with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the invalid escape sequence
content = content.replace(r"re.match(r'^\$?\s*\d{1,3}(?:\.\d{3})+(?:,\d{2})?$', cod)", r"re.match(r'^\\$?\s*\d{1,3}(?:\.\d{3})+(?:,\d{2})?$', cod)")
content = content.replace(r"re.match(r'^\$?\s*\d{1,3}(?:\.\d{3})+(?:,\d{2})?$', desc)", r"re.match(r'^\\$?\s*\d{1,3}(?:\.\d{3})+(?:,\d{2})?$', desc)")

with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
