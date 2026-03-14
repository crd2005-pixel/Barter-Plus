import re

with open("lubricentro/productos/codigos_barra.py", "r", encoding="utf-8") as f:
    cb = f.read()
    print("Códigos de Barra filters present?", "cb_filtro_rubro" in cb)
