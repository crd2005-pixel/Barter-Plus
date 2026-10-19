from unificador_listas.app import App
import math

app = App()

tests = [
    ("3 $ 9.025,70", 9025.7),
    ("Fco $ 1.500,00", 1500.0),
    ("$150", 150.0),
    ("150.50", 150.5)
]

for raw, expected in tests:
    res = app.limpiar_precio_argentino(raw)
    print(f"'{raw}' -> {res} (Expected: {expected})")
    if not math.isclose(res, expected):
        print("FAILED!")
