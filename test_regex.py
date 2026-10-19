import re

PATRON_MEMBRETE = re.compile(
    r'(tel\s*[:.]?|cel\s*[:.]?|fax|0260|0261|44\d[\s-]?\d{3}|sarmiento|san\s+rafael|mendoza|cuit|iva\s|www\.|http|@|distribuidora|hoja\s*\d|p[aá]gina)',
    re.IGNORECASE
)

tests = [
    "Tel : 0260-443 440",
    "Av. Sarmiento 263 - 5600 San Rafael - Mendoza",
    "www.abrazaderas.com",
    "ABRAZADERAS PERFECTO",
    "Standard Fleje 9mm",
    "Tornillo y Tuerca",
    "CODIGO | APLICAC. | PR"
]

for t in tests:
    print(f"'{t}' -> {bool(PATRON_MEMBRETE.search(t))}")
