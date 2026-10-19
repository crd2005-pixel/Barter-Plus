blacklist = ["av.", "avenida", "calle ", "san rafael", "mendoza", "tel:", "cel:", "cuit", "www.", "@", "distribuidora", "lista de precios", "vigencia", "5600", "5620"]
test_str = "Av. Sarmiento 263 - 5600 San Rafael - Mendoza"

lower_str = test_str.lower()
print(any(kw in lower_str for kw in blacklist))
