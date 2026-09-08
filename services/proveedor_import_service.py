import datetime as dt
from database.conexion import get_session
from database.models.producto import Producto, Marca, Categoria
from database.models.proveedor import Proveedor
from typing import List, Dict, Tuple
from sqlalchemy import select

class ProveedorImportService:
    @staticmethod
    def procesar_importacion_maestra(filas: List[Dict]) -> Tuple[int, int, int]:
        """
        Recibe una lista de diccionarios mapeados desde el Excel.
        Diccionario esperado:
        {
            'sku': str,
            'proveedor': str,
            'marca': str,
            'nombre': str,
            'costo': float
        }
        Realiza un UPSERT basado en el SKU.
        Retorna una tupla: (nuevos_creados, actualizados, errores)
        """
        nuevos = 0
        actualizados = 0
        errores = 0

        with get_session() as session:
            try:
                # Cachés para evitar múltiples consultas a la BD
                cache_proveedores = {p.nombre.lower(): p for p in session.scalars(select(Proveedor)).all() if p.nombre}

                # Fetch correctly using simple select
                stmt_marcas = select(Marca)
                todas_marcas = session.scalars(stmt_marcas).all()
                cache_marcas = {m.nombre.lower(): m for m in todas_marcas if m.nombre}

                # Cache productos by SKU for fast lookup
                stmt_productos = select(Producto)
                todos_productos = session.scalars(stmt_productos).all()
                cache_productos = {p.sku.lower(): p for p in todos_productos if p.sku}

                for row in filas:
                    try:
                        sku_val = str(row.get('sku', '')).strip()
                        if not sku_val:
                            continue

                        costo_val = float(row.get('costo', 0.0))
                        nombre_val = str(row.get('nombre', '')).strip()
                        prov_nombre = str(row.get('proveedor', '')).strip()
                        marca_nombre = str(row.get('marca', '')).strip()

                        # 1. Resolver Proveedor
                        prov_obj = None
                        if prov_nombre:
                            prov_key = prov_nombre.lower()
                            if prov_key not in cache_proveedores:
                                prov_obj = Proveedor(nombre=prov_nombre)
                                session.add(prov_obj)
                                session.flush()
                                cache_proveedores[prov_key] = prov_obj
                            prov_obj = cache_proveedores[prov_key]

                        # 2. Resolver Marca
                        marca_obj = None
                        if marca_nombre:
                            marca_key = marca_nombre.lower()
                            if marca_key not in cache_marcas:
                                marca_obj = Marca(nombre=marca_nombre)
                                session.add(marca_obj)
                                session.flush()
                                cache_marcas[marca_key] = marca_obj
                            marca_obj = cache_marcas[marca_key]

                        # 3. UPSERT Producto
                        sku_key = sku_val.lower()
                        if sku_key in cache_productos:
                            # Update
                            prod = cache_productos[sku_key]
                            prod.costo = costo_val
                            if nombre_val:
                                prod.nombre = nombre_val
                            if prov_obj:
                                prod.proveedor_id = prov_obj.id
                            if marca_obj:
                                prod.marca_id = marca_obj.id
                            prod.actualizado_en = dt.datetime.utcnow()
                            actualizados += 1
                        else:
                            # Insert
                            nuevo_prod = Producto(
                                sku=sku_val,
                                nombre=nombre_val if nombre_val else f"Producto {sku_val}",
                                costo=costo_val,
                                proveedor_id=prov_obj.id if prov_obj else None,
                                marca_id=marca_obj.id if marca_obj else None,
                                activo=True
                            )
                            session.add(nuevo_prod)
                            cache_productos[sku_key] = nuevo_prod
                            nuevos += 1

                    except Exception as e:
                        # Log individual row errors if needed
                        errores += 1
                        continue

                session.commit()
                return nuevos, actualizados, errores

            except Exception as e:
                session.rollback()
                raise e
