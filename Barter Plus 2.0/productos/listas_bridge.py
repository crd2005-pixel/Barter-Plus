# -*- coding: utf-8 -*-
"""
productos/listas_bridge.py

Puente de lectura: obtiene para un producto el precio base de lista y aplica
los % guardados por LISTA y por MARCA (proveedores/costos.py) para calcular:
- base (precio de costo de la lista)
- con_desc (precio con descuento)
- mas_iva (+IVA final de lista)

Emparejamiento (prioridad):
1) proveedor_id + codigo en las listas de ese proveedor (de la más nueva a la más vieja)
2) codigo en todas las listas
3) nombre exacto en todas las listas

Además, expone get_stock_qty_for_product() para leer stock del producto.
"""

from sqlalchemy import select, or_
from db import SessionLocal as AppSession
from .listas_cache import ListasCache

_cache = ListasCache()

_ns_cache = None
def _get_ns():
    global _ns_cache
    if _ns_cache is None:
        from proveedores.bootstrap import bootstrap
        _ns_cache = bootstrap()
    return _ns_cache

def enable_cache():
    _cache.load()

def _s(val):
    try:
        return (val or "").strip()
    except Exception:
        try:
            return str(val).strip()
        except Exception:
            return ""

def _num(x):
    s = str(x).strip()
    if s == "":
        return 0.0
    try:
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s and "." not in s:
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        try:
            return float(x)
        except Exception:
            return 0.0

def _get_attr(obj, *names):
    for n in names:
        if hasattr(obj, n):
            v = getattr(obj, n)
            if v is not None:
                return v
    return None

def find_price_plus_iva_for_product(producto) -> dict:
    from productos.utils import costo_proveedor_iva_descuento

    base, iva_pct, desc_pct = costo_proveedor_iva_descuento(producto)

    # Calculate con_desc and mas_iva
    con_desc = base * (1.0 - (desc_pct / 100.0))
    mas_iva = con_desc * (1.0 + (iva_pct / 100.0))

    marca = getattr(producto, 'marca', '')
    if hasattr(producto, 'marca_rel') and producto.marca_rel:
        marca = producto.marca_rel.nombre

    codigo = getattr(producto, 'codigo_proveedor', None)
    if not codigo:
        codigo = getattr(producto, 'codigo', getattr(producto, 'sku', ''))

    return {
        "ok": True,
        "lista_id": None,
        "proveedor_id": getattr(producto, 'proveedor_id', None),
        "base": base,
        "con_desc": con_desc,
        "mas_iva": mas_iva,
        "desc_pct": desc_pct,
        "iva_pct": iva_pct,
        "marca": marca,
        "codigo": codigo,
        "descripcion_lista": getattr(producto, 'nombre', ''),
        "presentacion": getattr(producto, 'presentacion_unidad', ''),
        "info_extra": ""
    }
def get_stock_qty_for_product(producto) -> float:
    """
    Lee stock desde:
    - atributo del Producto (stock|cantidad|existencia|qty)
    - o tabla Stock(producto_id,cantidad) si existe en db
    """
    q = _get_attr(producto, "stock", "cantidad", "existencia", "qty")
    if q is not None:
        try:
            return float(q)
        except Exception:
            pass
    try:
        from db import Stock  # si existe
        with AppSession() as s:
            row = s.query(Stock).filter(getattr(Stock, "producto_id") == getattr(producto, "id", None)).first()
            if row is not None:
                v = getattr(row, "cantidad", None) or getattr(row, "stock", None) or getattr(row, "qty", None)
                return float(v or 0.0)
    except Exception:
        pass
    return 0.0
