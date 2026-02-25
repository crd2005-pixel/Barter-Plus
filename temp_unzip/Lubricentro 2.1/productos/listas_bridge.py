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
    """
    Retorna:
    {
      "ok": bool,
      "lista_id": int|None,
      "proveedor_id": int|None,
      "base": float,
      "con_desc": float,
      "mas_iva": float,
      "desc_pct": float,
      "iva_pct": float,
      "marca": str,
      "codigo": str,
      "descripcion_lista": str,
      "presentacion": str,
      "info_extra": str
    }
    Optimized version: Single query across all lists.
    """
    from proveedores.costos import get_lista_percents, get_marca_percents, calc_line

    _ns = _get_ns()
    ListaPrecioProveedor = _ns["ListaPrecioProveedor"]
    ItemListaProveedor = _ns["ItemListaProveedor"]
    ProvSession = _ns["SessionLocal"]

    if not ProvSession:
        return {"ok": False, "lista_id": None, "proveedor_id": None, "base": 0.0, "con_desc": 0.0, "mas_iva": 0.0,
                "desc_pct": 0.0, "iva_pct": 0.0, "marca": "", "codigo": "", "descripcion_lista": "Error conexión DB",
                "presentacion": "", "info_extra": ""}

    # Priority: codigo_proveedor > codigo (generic) > nombre
    cod_prov = _s(_get_attr(producto, "codigo_proveedor"))
    sku = _s(_get_attr(producto, "codigo", "sku", "cod"))
    nombre = _s(_get_attr(producto, "nombre"))
    proveedor_id = _get_attr(producto, "proveedor_id")

    # If explicit provider code is set, we prefer only that (strict mode usually).
    # But if we want to be robust, we can search others as fallback within the query logic.
    force_code_only = bool(cod_prov)

    # --- CACHE CHECK ---
    if _cache.loaded:
        best_row = _cache.find_match(cod_prov, sku, nombre, proveedor_id)
        if best_row:
             d, v = get_lista_percents(best_row["lista_id"])
             md, mv = get_marca_percents(best_row["lista_id"], best_row["marca"])
             if md is not None: d = md
             if mv is not None: v = mv
             base, con_desc, mas_iva = calc_line(best_row["base"], d, v)

             return {
                "ok": True,
                "lista_id": best_row["lista_id"],
                "proveedor_id": best_row["proveedor_id"],
                "base": base,
                "con_desc": con_desc,
                "mas_iva": mas_iva,
                "desc_pct": d,
                "iva_pct": v,
                "marca": best_row["marca"],
                "codigo": best_row["codigo"],
                "descripcion_lista": best_row["desc"],
                "presentacion": best_row["pres"],
                "info_extra": best_row["extra"]
             }
        else:
             return {"ok": False, "lista_id": None, "proveedor_id": None, "base": 0.0, "con_desc": 0.0, "mas_iva": 0.0,
                "desc_pct": 0.0, "iva_pct": 0.0, "marca": "", "codigo": sku or cod_prov or "",
                "descripcion_lista": "", "presentacion": "", "info_extra": ""}
    # --- END CACHE CHECK ---

    # Identify dynamic columns
    code_col  = getattr(ItemListaProveedor, "producto_codigo", None) or getattr(ItemListaProveedor, "codigo")
    price_col = getattr(ItemListaProveedor, "precio", None) or getattr(ItemListaProveedor, "prec")
    desc_col  = getattr(ItemListaProveedor, "descripcion")
    marca_col = getattr(ItemListaProveedor, "marca")
    pres_col  = getattr(ItemListaProveedor, "presentacion", None)
    extra_col = getattr(ItemListaProveedor, "info_extra", None)

    with ProvSession() as ps:
        # Build optimized query
        # We join ListaPrecioProveedor to filter by provider or just to get the provider_id and date.
        # We order by ListaPrecioProveedor.id DESC to prioritize newest lists.

        sel = [
            code_col, desc_col, marca_col, price_col,
            ListaPrecioProveedor.id, ListaPrecioProveedor.proveedor_id
        ]
        if pres_col is not None: sel.append(pres_col)
        if extra_col is not None: sel.append(extra_col)

        stmt = select(*sel).join(ListaPrecioProveedor, ItemListaProveedor.lista_id == ListaPrecioProveedor.id)

        # Conditions
        conditions = []

        if cod_prov:
            conditions.append(code_col == cod_prov)
            # También permitimos que el código guardado coincida con la descripción (para ítems sin código)
            conditions.append(desc_col == cod_prov)

        if not force_code_only:
            if sku:
                conditions.append(code_col == sku)
            if nombre:
                conditions.append(desc_col == nombre)
                # IMPORTANT: Support "Description as Code" case.
                # If imported items have code=desc, and product has name=desc, we want to match.
                conditions.append(code_col == nombre)

        if not conditions:
            # Nothing to search for
            return {"ok": False, "lista_id": None, "proveedor_id": None, "base": 0.0, "con_desc": 0.0, "mas_iva": 0.0,
                    "desc_pct": 0.0, "iva_pct": 0.0, "marca": "", "codigo": sku or cod_prov or "",
                    "descripcion_lista": "", "presentacion": "", "info_extra": ""}

        stmt = stmt.where(or_(*conditions))

        if proveedor_id:
            stmt = stmt.where(ListaPrecioProveedor.proveedor_id == int(proveedor_id))

        stmt = stmt.order_by(ListaPrecioProveedor.id.desc()).limit(100) # Limit to avoid fetching massive data if many matches

        rows = ps.execute(stmt).all()

        # In memory filtering for best match
        # Priorities:
        # 1. Newest List (Already handled by order_by)
        # 2. Within same list (or generally, if we trust order_by):
        #    - Match on code_prov
        #    - Match on sku
        #    - Match on name (desc or code=desc)

        best_row = None
        best_priority = 999

        # Priority mapping
        # 0: Explicit Code (cod_prov) matches Item.Code
        # 1: SKU matches Item.Code
        # 2: Name matches Item.Code (Desc as Code)
        # 3: Name matches Item.Desc

        for row in rows:
            # Unpack
            r_code = _s(row[0])
            r_desc = _s(row[1])
            r_marca = _s(row[2])
            r_base = _num(row[3])
            r_lid = int(row[4])
            r_pid = int(row[5])

            idx = 6
            r_pres = ""
            r_extra = ""
            if pres_col is not None:
                r_pres = _s(row[idx]); idx += 1
            if extra_col is not None:
                r_extra = _s(row[idx]); idx += 1

            # Determine match quality
            prio = 999

            if cod_prov and r_code == cod_prov:
                prio = 0
            elif cod_prov and r_desc == cod_prov:
                prio = 0  # Treat description match as strong link if explicitly stored in cod_prov
            elif not force_code_only:
                if sku and r_code == sku:
                    prio = 1
                elif nombre and r_code == nombre:
                    prio = 2
                elif nombre and r_desc == nombre:
                    prio = 3

            if prio == 999: continue # Should not happen given the WHERE clause but good for safety

            # Since rows are ordered by List ID DESC (Newest first),
            # the first row we see is from the newest list.
            # If we see multiple matches from the SAME list (unlikely with LIMIT 1 usually, but possible),
            # we want the best priority.
            # If we see a match from an OLDER list, should we take it if it has better priority?
            # Typically: Newest Price is king.
            # BUT if I have an explicit Code match in an old list, and a Name match in a new list...
            # User probably wants the Linked Item (Code match).

            # So: Best Priority > Newest List.

            if best_row is None or prio < best_priority:
                best_row = {
                    "lista_id": r_lid,
                    "proveedor_id": r_pid,
                    "base": r_base,
                    "marca": r_marca,
                    "codigo": r_code,
                    "desc": r_desc,
                    "pres": r_pres,
                    "extra": r_extra
                }
                best_priority = prio

            if best_priority == 0:
                break # Cannot beat 0

        if best_row:
            d, v = get_lista_percents(best_row["lista_id"])
            md, mv = get_marca_percents(best_row["lista_id"], best_row["marca"])
            if md is not None: d = md
            if mv is not None: v = mv
            base, con_desc, mas_iva = calc_line(best_row["base"], d, v)

            return {
                "ok": True,
                "lista_id": best_row["lista_id"],
                "proveedor_id": best_row["proveedor_id"],
                "base": base,
                "con_desc": con_desc,
                "mas_iva": mas_iva,
                "desc_pct": d,
                "iva_pct": v,
                "marca": best_row["marca"],
                "codigo": best_row["codigo"],
                "descripcion_lista": best_row["desc"],
                "presentacion": best_row["pres"],
                "info_extra": best_row["extra"]
            }

    return {"ok": False, "lista_id": None, "proveedor_id": None, "base": 0.0, "con_desc": 0.0, "mas_iva": 0.0,
            "desc_pct": 0.0, "iva_pct": 0.0, "marca": "", "codigo": cod_prov or sku, "descripcion_lista": "",
            "presentacion": "", "info_extra": ""}

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
