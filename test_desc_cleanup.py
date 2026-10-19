from unificador_listas.app import App
app = App()

tests = [
    ("300003      Trabasil RM1", "300003", "Trabasil RM1"),
    ("98-016 - ABRAZADERAS - 8- 16", "98-016", "ABRAZADERAS - 8- 16"),
    ("ABRAZADERAS PERFECTO", "98-016", "ABRAZADERAS PERFECTO"),
    ("   Muchos    espacios  ", "NONE", "Muchos espacios")
]

for desc, cod, expected in tests:
    res = app.limpiar_descripcion_final(desc, cod)
    print(f"'{desc}' -> '{res}' (Expected: '{expected}')")
    assert res == expected, f"Failed: {res} != {expected}"
