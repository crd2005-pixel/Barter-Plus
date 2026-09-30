import re

with open("services/dashboard_service.py", "r") as f:
    content = f.read()

replacement = """    @staticmethod
    def obtener_valor_inventario() -> dict:
        with get_session() as session:
            # Extraer ambos totales usando COALESCE para evitar nulos
            stmt = select(
                func.sum(func.coalesce(Producto.costo, 0) * Producto.stock_actual).label("capital_invertido"),
                func.sum(func.coalesce(Producto.precio_minorista, 0) * Producto.stock_actual).label("valor_venta_publico")
            ).where(Producto.stock_actual > 0)

            res = session.execute(stmt).first()
            if res:
                capital_invertido = res.capital_invertido or 0.0
                valor_venta = res.valor_venta_publico or 0.0
            else:
                capital_invertido = 0.0
                valor_venta = 0.0

            return {
                "capital_invertido": capital_invertido,
                "valor_venta_publico": valor_venta
            }"""

content = re.sub(r'    @staticmethod\n    def obtener_valor_inventario\(\) -> float:.*?            return valor or 0\.0', replacement, content, flags=re.DOTALL)

with open("services/dashboard_service.py", "w") as f:
    f.write(content)
