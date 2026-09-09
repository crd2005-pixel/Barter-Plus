from database.conexion import get_session
from database.models.producto import Producto
from typing import Optional, List
from sqlalchemy import select

class ProductoService:
    @staticmethod
    def calcular_precio_final(costo: float, margen: float) -> float:
        """
        Calcula el precio final usando la fórmula financiera de margen estricta:
        PF = PM / (1 - (Margen / 100))
        Donde PM es el costo base.
        Incluye redondeo de negocio:
        - Si PF <= 6000: redondea a la centena superior.
        - Si PF > 6000: redondea al millar superior.
        """
        import math

        if margen >= 100:
            raise ValueError("El margen no puede ser del 100% o superior, causa división por cero.")

        if margen == 0:
            pf = costo
        else:
            pf = costo / (1 - (margen / 100))

        # Regla de Redondeo de Negocio
        if pf <= 6000:
            # Redondeo a la centena superior
            pf_redondeado = math.ceil(pf / 100.0) * 100.0
        else:
            # Redondeo al millar superior
            pf_redondeado = math.ceil(pf / 1000.0) * 1000.0

        return pf_redondeado

    @staticmethod
    def crear_producto(nombre: str, costo: float, iva: float = 21.0,
                       codigo_barras: Optional[str] = None,
                       stock_inicial: float = 0.0,
                       es_granel: bool = False,
                       divisor_granel: float = 1.0,
                       stock_minimo: float = 0.0,
                       stock_maximo: float = 0.0,
                       sku: Optional[str] = None,
                       proveedor_nombre: Optional[str] = None,
                       categoria_nombre: Optional[str] = None,
                       marca_nombre: Optional[str] = None) -> Producto:
        from database.models.producto import Categoria, Marca
        from database.models.proveedor import Proveedor
        with get_session() as session:
            try:
                # Creación dinámica de categoría si no existe
                cat_id = None
                if categoria_nombre and categoria_nombre.strip() and categoria_nombre not in ("-- Ninguna --", "-- Seleccionar --"):
                    cat_nom = categoria_nombre.strip()
                    categoria = session.query(Categoria).filter(Categoria.nombre.ilike(cat_nom)).first()
                    if not categoria:
                        categoria = Categoria(nombre=cat_nom)
                        session.add(categoria)
                        session.flush()
                    cat_id = categoria.id

                # Creación dinámica de marca si no existe
                mar_id = None
                if marca_nombre and marca_nombre.strip() and marca_nombre not in ("-- Ninguna --", "-- Seleccionar --"):
                    mar_nom = marca_nombre.strip()
                    marca = session.query(Marca).filter(Marca.nombre.ilike(mar_nom)).first()
                    if not marca:
                        marca = Marca(nombre=mar_nom)
                        session.add(marca)
                        session.flush()
                    mar_id = marca.id

                # Creación dinámica de proveedor si no existe
                prov_id = None
                if proveedor_nombre and proveedor_nombre.strip() and proveedor_nombre not in ("-- Ninguno --", "-- Seleccionar --"):
                    prov_nom = proveedor_nombre.strip()
                    proveedor = session.query(Proveedor).filter(Proveedor.nombre.ilike(prov_nom)).first()
                    if not proveedor:
                        proveedor = Proveedor(nombre=prov_nom)
                        session.add(proveedor)
                        session.flush()
                    prov_id = proveedor.id

                nuevo_producto = Producto(
                    sku=sku,
                    nombre=nombre,
                    costo=costo,
                    iva=iva,
                    codigo_barras=codigo_barras,
                    stock_actual=stock_inicial,
                    stock_minimo=stock_minimo,
                    stock_maximo=stock_maximo,
                    es_granel=es_granel,
                    divisor_granel=divisor_granel,
                    proveedor_id=prov_id,
                    categoria_id=cat_id,
                    marca_id=mar_id
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

                pf = ProductoService.calcular_precio_final(producto.costo, margen)
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
                                data['costo'], data['margen']
                            )
                        count += 1
                session.commit()
                return count
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def calcular_margen_inverso(costo: float, precio_final: float) -> float:
        """
        Calcula el margen aplicado dado un costo base y un precio final.
        Fórmula: Margen = (1 - (PM / PF)) * 100
        Donde PM = costo
        """
        if costo <= 0 or precio_final <= 0:
            return 0.0

        if costo >= precio_final:
            return 0.0 # Caso atípico o sin margen

        margen = (1 - (costo / precio_final)) * 100
        return round(margen, 2)

    @staticmethod
    def obtener_sugerencias_pedido() -> List[dict]:
        """
        Retorna la lista de productos que requieren reposición de stock.
        Reglas de Reabastecimiento:
        A) stock_actual <= stock_minimo (siempre que mínimo > 0)
        B) stock_actual <= 0 (incluso si mínimo es 0 o nulo)
        Fórmula matemática de pedido:
        Cantidad a Pedir = stock_maximo - stock_actual
        """
        from sqlalchemy.orm import joinedload
        with get_session() as session:
            stmt = select(Producto).options(
                joinedload(Producto.proveedor),
                joinedload(Producto.marca)
            ).where(Producto.activo == True)

            productos_activos = session.scalars(stmt).all()
            sugerencias = []

            for p in productos_activos:
                pedir = False

                if p.stock_actual <= 0:
                    pedir = True
                elif p.stock_minimo > 0 and p.stock_actual <= p.stock_minimo:
                    pedir = True

                if pedir:
                    # Aplicar fórmula estricta
                    cantidad_pedir = p.stock_maximo - p.stock_actual
                    if cantidad_pedir <= 0:
                        cantidad_pedir = 1.0 # Pedido mínimo por seguridad si máximo está mal configurado

                    sugerencias.append({
                        'producto': p,
                        'cantidad_pedir': cantidad_pedir
                    })

            for s in sugerencias:
                session.expunge(s['producto'])

            return sugerencias

    @staticmethod
    def actualizar_producto_manual(producto_id: int, nombre: str, codigo_barras: str, costo: float,
                                   margen: float, stock: float, es_granel: bool = False,
                                   divisor_granel: float = 1.0, stock_minimo: float = 0.0,
                                   stock_maximo: float = 0.0, proveedor_nombre: Optional[str] = None,
                                   categoria_nombre: Optional[str] = None, marca_nombre: Optional[str] = None) -> Optional[Producto]:
        from database.models.producto import Categoria, Marca
        from database.models.proveedor import Proveedor
        with get_session() as session:
            try:
                producto = session.get(Producto, producto_id)
                if not producto:
                    return None

                # Creación dinámica de categoría si no existe
                cat_id = None
                if categoria_nombre and categoria_nombre.strip() and categoria_nombre not in ("-- Ninguna --", "-- Seleccionar --"):
                    cat_nom = categoria_nombre.strip()
                    categoria = session.query(Categoria).filter(Categoria.nombre.ilike(cat_nom)).first()
                    if not categoria:
                        categoria = Categoria(nombre=cat_nom)
                        session.add(categoria)
                        session.flush()
                    cat_id = categoria.id

                # Creación dinámica de marca si no existe
                mar_id = None
                if marca_nombre and marca_nombre.strip() and marca_nombre not in ("-- Ninguna --", "-- Seleccionar --"):
                    mar_nom = marca_nombre.strip()
                    marca = session.query(Marca).filter(Marca.nombre.ilike(mar_nom)).first()
                    if not marca:
                        marca = Marca(nombre=mar_nom)
                        session.add(marca)
                        session.flush()
                    mar_id = marca.id

                # Creación dinámica de proveedor si no existe
                prov_id = None
                if proveedor_nombre and proveedor_nombre.strip() and proveedor_nombre not in ("-- Ninguno --", "-- Seleccionar --"):
                    prov_nom = proveedor_nombre.strip()
                    proveedor = session.query(Proveedor).filter(Proveedor.nombre.ilike(prov_nom)).first()
                    if not proveedor:
                        proveedor = Proveedor(nombre=prov_nom)
                        session.add(proveedor)
                        session.flush()
                    prov_id = proveedor.id

                producto.nombre = nombre
                producto.codigo_barras = codigo_barras if codigo_barras else None
                producto.proveedor_id = prov_id
                producto.categoria_id = cat_id
                producto.marca_id = mar_id
                producto.costo = costo
                producto.stock_actual = stock
                producto.stock_minimo = stock_minimo
                producto.stock_maximo = stock_maximo
                producto.es_granel = es_granel
                producto.divisor_granel = divisor_granel

                pf = ProductoService.calcular_precio_final(costo, margen)
                producto.precio_minorista = pf

                session.commit()
                session.refresh(producto)
                session.expunge(producto)
                return producto
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def buscar_por_query_flexible(query: str) -> Optional[Producto]:
        """
        Busca un producto por código de barras, SKU interno o coincidencia parcial de nombre.
        """
        from sqlalchemy.orm import joinedload
        with get_session() as session:
            stmt = select(Producto).options(
                joinedload(Producto.categoria),
                joinedload(Producto.marca),
                joinedload(Producto.proveedor)
            ).where(
                (Producto.codigo_barras == query) |
                (Producto.sku == query) |
                (Producto.nombre.icontains(query))
            )
            producto = session.scalars(stmt).first()
            if producto:
                session.expunge(producto)
            return producto

    @staticmethod
    def agregar_pedido_manual(detalle: str) -> None:
        from database.models.contabilidad import PedidoManual
        with get_session() as session:
            try:
                pedido = PedidoManual(detalle=detalle)
                session.add(pedido)
                session.commit()
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def listar_nombres() -> List[str]:
        with get_session() as session:
            return session.scalars(select(Producto.nombre)).all()

    @staticmethod
    def obtener_diccionarios_relaciones() -> tuple[list[dict], list[dict], list[dict]]:
        """Devuelve listas de dicts para Proveedores, Categorias y Marcas para popular combos."""
        from database.models.proveedor import Proveedor
        from database.models.producto import Categoria, Marca
        with get_session() as session:
            provs = [{"id": p.id, "nombre": p.nombre} for p in session.scalars(select(Proveedor)).all()]
            cats = [{"id": c.id, "nombre": c.nombre} for c in session.scalars(select(Categoria)).all()]
            marcas = [{"id": m.id, "nombre": m.nombre} for m in session.scalars(select(Marca)).all()]
            return provs, cats, marcas
