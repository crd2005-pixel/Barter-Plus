# -*- coding: utf-8 -*-
# ventas/precio_busquedas.py
from typing import Optional
import traceback
from db import SessionLocal, Producto

# Puente oficial presente en tu 1.7.x (y 1.6.x)
from ventas.precio_vigente_bridge import (
    calcular_parametros as _calc_params,
    get_precio_vigente_por_producto as _vigente_for_prod,
)

# Campos comunes de códigos; agregá aquí si usás otro nombre
_CODE_FIELDS = (
    "codigo_barras", "codigo_barra", "barcode", "cb", "ean",
    "codigo", "codigo_interno", "cod", "sku", "codigo_proveedor"
)

def find_producto_robusto(session, token: str) -> Optional[Producto]:
    t = (token or "").strip()
    if not t:
        return None

    # 1) ID exacto
    try:
        pid = int(t)
        p = session.query(Producto).get(pid)
        if p:
            return p
    except Exception:
        pass

    # 2) Código exacto
    for fn in _CODE_FIELDS:
        col = getattr(Producto, fn, None)
        if col is not None:
            pr = session.query(Producto).filter(col == t).first()
            if pr:
                return pr

    # 3) Nombre exacto
    pr = session.query(Producto).filter(Producto.nombre == t).first()
    if pr:
        return pr

    # 4) Aproximado: nombre
    try:
        pr = session.query(Producto).filter(Producto.nombre.ilike(f"%{t}%")).first()
    except Exception:
        pr = session.query(Producto).filter(Producto.nombre.contains(t)).first()
    if pr:
        return pr

    # 5) Aproximado: otros códigos de texto
    for fn in ("codigo", "codigo_interno", "sku", "codigo_proveedor"):
        col = getattr(Producto, fn, None)
        if col is not None:
            try:
                pr = session.query(Producto).filter(col.ilike(f"%{t}%")).first()
            except Exception:
                pr = session.query(Producto).filter(col.contains(t)).first()
            if pr:
                return pr

    return None


def precio_final_lista(session, p, params=None) -> float:
    """
    'Precio Final' de Productos/Precios (sin promo).
    Usa función base del puente si está disponible; si no, cae a campos comunes.
    """
    try:
        import ventas.precio_vigente_bridge as br
        fn = getattr(br, "_precio_final_base", None)
        if callable(fn):
            pms = params or _calc_params(session)
            val = float(fn(p, pms["total_fijos"], pms["denom_total"], pms["ganancia_pct"]))
            if val > 0:
                return val
    except Exception:
        traceback.print_exc()

    for fname in ("precio", "precio_final", "precio_venta", "precio_minorista"):
        if hasattr(p, fname):
            try:
                return float(getattr(p, fname) or 0.0)
            except Exception:
                pass
    return 0.0


def precio_vigente(session, p, params=None) -> float:
    """
    PROMO vigente si existe; si no, Precio Final.
    """
    params = params or _calc_params(session)
    try:
        val, _src = _vigente_for_prod(session, p, params)
        if val is not None:
            return float(val)
    except Exception:
        pass
    return float(precio_final_lista(session, p, params) or 0.0)


# Alias expuesto para usar desde otras pantallas
calcular_parametros = _calc_params
