from database.conexion import get_session
from database.models.producto import Producto
from typing import Optional, List
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
                    stock_maximo=stock_inicial
                )
                session.add(nuevo_producto)
                session.commit()
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

    @staticmethod
    def buscar_por_id(producto_id: int) -> Optional[Producto]:
        with get_session() as session:
            producto = session.get(Producto, producto_id)
            if producto:
                session.expunge(producto)
            return producto

    @staticmethod
    def listar_todos(busqueda: str = "") -> List[Producto]:
        from sqlalchemy.orm import joinedload
        with get_session() as session:
            stmt = select(Producto).options(
                joinedload(Producto.categoria),
                joinedload(Producto.marca),
                joinedload(Producto.proveedor)
            )
            if busqueda:
                stmt = stmt.where(Producto.nombre.icontains(busqueda) | Producto.codigo_barras.icontains(busqueda))
            productos = session.scalars(stmt).all()
            for p in productos:
                session.expunge(p)
            return list(productos)

    @staticmethod
    def actualizar_precios_masivo(actualizaciones: List[dict]) -> int:
        """
        Aplica un batch de actualizaciones a la base de datos de forma segura.
        `actualizaciones` debe ser una lista de diccionarios:
        [{'id': int, 'costo': float, 'margen': float, 'precio_minorista': float}, ...]
        Retorna la cantidad de productos actualizados.
        """
        count = 0
        with get_session() as session:
            try:
                for data in actualizaciones:
                    producto = session.get(Producto, data['id'])
                    if producto:
                        # Si se pasa el costo nuevo
                        if 'costo' in data:
                            producto.costo = data['costo']
                        # Si se pasa un precio minorista ya calculado
                        # o si se debe calcular a partir de un margen
                        if 'precio_minorista' in data:
                            producto.precio_minorista = data['precio_minorista']
                        elif 'margen' in data and 'costo' in data:
                            producto.precio_minorista = ProductoService.calcular_precio_final(
                                data['costo'], producto.iva, data['margen']
                            )
                        count += 1
                session.commit()
                return count
            except Exception as e:
                session.rollback()
                raise e
