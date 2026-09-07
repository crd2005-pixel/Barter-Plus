from database.conexion import get_session
from database.models.producto import Producto
from typing import Optional
from sqlalchemy import select

class ProductoService:
    @staticmethod
    def calcular_precio_final(costo: float, iva: float, margen: float) -> float:
        """
        Calcula el precio final usando la fórmula financiera de margen estricta:
        PF = PM / (1 - (Margen / 100))
        Donde PM (Precio Mayorista) = costo * (1 + (iva / 100))
        """
        if margen >= 100:
            raise ValueError("El margen no puede ser del 100% o superior, causa división por cero.")

        precio_mayorista = costo * (1 + (iva / 100))
        if margen == 0:
            return precio_mayorista

        precio_final = precio_mayorista / (1 - (margen / 100))
        return round(precio_final, 2)

    @staticmethod
    def crear_producto(nombre: str, costo: float, iva: float = 21.0,
                       codigo_barras: Optional[str] = None,
                       stock_inicial: float = 0.0) -> Producto:
        with get_session() as session:
            try:
                nuevo_producto = Producto(
                    nombre=nombre,
                    costo=costo,
                    iva=iva,
                    codigo_barras=codigo_barras,
                    # Se usa stock_maximo temporalmente en pruebas para representar stock actual,
                    # dado que el modelo actual no lo posee.
                    stock_maximo=stock_inicial
                )
                session.add(nuevo_producto)
                session.commit()
                # Refrescar y luego 'expunge' para poder usar el objeto fuera de la sesión
                session.refresh(nuevo_producto)
                session.expunge(nuevo_producto)
                return nuevo_producto
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def actualizar_precio(producto_id: int, margen: float) -> Optional[Producto]:
        with get_session() as session:
            try:
                producto = session.get(Producto, producto_id)
                if not producto:
                    return None

                pf = ProductoService.calcular_precio_final(producto.costo, producto.iva, margen)
                producto.precio_minorista = pf

                session.commit()
                session.refresh(producto)
                session.expunge(producto)
                return producto
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def buscar_por_codigo(codigo_barras: str) -> Optional[Producto]:
        with get_session() as session:
            stmt = select(Producto).where(Producto.codigo_barras == codigo_barras)
            producto = session.scalars(stmt).first()
            if producto:
                session.expunge(producto)
            return producto
