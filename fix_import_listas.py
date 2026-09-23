import re

with open('lubricentro/proveedores/import_listas.py', 'r') as f:
    content = f.read()

content = content.replace('f"Proceso finalizado con éxito.\n\nActualizados: {actualizados}\nNuevos: {nuevos}"', 'f"Proceso finalizado con éxito.\\n\\nActualizados: {actualizados}\\nNuevos: {nuevos}"')

# Also replace the exact unescaped multiline if present:
broken_fstring = 'f"Proceso finalizado con éxito.\n\nActualizados: {actualizados}\nNuevos: {nuevos}"'
if 'f"Proceso finalizado con éxito.\n\nActualizados' in content:
    content = re.sub(r'f"Proceso finalizado con éxito\.\n\nActualizados: \{actualizados\}\nNuevos: \{nuevos\}"', 'f"Proceso finalizado con éxito.\\n\\nActualizados: {actualizados}\\nNuevos: {nuevos}"', content)

with open('lubricentro/proveedores/import_listas.py', 'w') as f:
    f.write(content)
