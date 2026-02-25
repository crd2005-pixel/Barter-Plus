# -*- coding: utf-8 -*-
"""
ventas/precio_vigente_bridge.py

Bloque de apoyo: calcula el PRECIO VIGENTE de un producto para Ventas.
Prioridad:
  1) Promoción vigente (valor > 0 y hoy ∈ [inicio, fin]).
     - tipo 'fijo'        => precio = base - valor ($)
     - tipo 'porcentaje'  => precio = base * (1 - valor/100)
  2) Precio Final (Productos→Precios): (mas_iva + prorrateo) / (1 - ganancia)

Uso:
  from ventas.precio_vigente_bridge import calcular_parametros, get_precio_vigente_por_producto
  with SessionLocal() as s:
      params = calcular_parametros(s)      # opcional (mejor rendimiento en listados)
      precio, fuente = get_precio_vigente_por_producto(s, producto, params)
"""

from datetime import date
from typing import Optional, Tuple, Dict

from PyQt5.QtCore import QSettings
from sqlalchemy import or_

from db import SessionLocal, Producto

# Modelo de promociones
from db.models.productos import PromocionProducto

# Utilidades usadas también por Productos→Precios
from productos.listas_bridge import find_price_plus_iva_for_product, get_stock_qty_for_product, enable_cache

from productos.utils import total_prorrateable_mes as _total_prorrateable_mes


def _leer_ganancia_pct() -> float:
    try:
        st = QSettings("BarterPlus", "BarterPlus")
        val = st.value("productos/precios/ganancia_pct", None)
        return float(val) if val is not None else 0.0
    except Exception:
        return 0.0


def _denominador_total(session) -> float:
    denom = 0.0
    for p in session.query(Producto).all():
        try:
            info = find_price_plus_iva_for_product(p) or {}
            mas_iva = float(info.get("mas_iva", 0.0)) if isinstance(info, dict) else float(info or 0.0)
        except Exception:
            mas_iva = 0.0
        try:
            stk = float(get_stock_qty_for_product(p) or 0.0)
        except Exception:
            stk = 0.0
        if mas_iva > 0 and stk > 0:
            denom += (mas_iva * stk)
    return denom


def calcular_parametros(session) -> Dict[str, float]:
    """ Calcula una sola vez los parámetros usados por muchos productos. """
    enable_cache()
    total_fijos = float(_total_prorrateable_mes() or 0.0)
    denom_total = _denominador_total(session)
    ganancia_pct = _leer_ganancia_pct()
    return {"total_fijos": total_fijos, "denom_total": denom_total, "ganancia_pct": ganancia_pct}


def _precio_final_base(p: Producto, total_fijos: float, denom_total: float, ganancia_pct: float) -> float:
    """ Precio Final (el de Productos→Precios, sin promo). """
    try:
        info = find_price_plus_iva_for_product(p) or {}
        mas_iva = float(info.get("mas_iva", 0.0)) if isinstance(info, dict) else float(info or 0.0)
    except Exception:
        mas_iva = 0.0
    try:
        stk = float(get_stock_qty_for_product(p) or 0.0)
    except Exception:
        stk = 0.0

    prorr = 0.0
    if denom_total > 0 and mas_iva > 0 and stk > 0:
        prorr = total_fijos * ((mas_iva * stk) / denom_total)

    precio_cp = mas_iva + prorr
    gan = max(0.0, min(500.0, float(ganancia_pct))) / 100.0

    # Precio final por presentación completa
    final_full = float(precio_cp / (1.0 - gan)) if (1.0 - gan) > 1e-9 else float(precio_cp)

    # Si es venta a granel, dividir por la presentación
    # (ej: precio de tambor 200L -> precio por litro)
    try:
        is_granel = False
        if hasattr(p, "venta_granel"):
            is_granel = bool(getattr(p, "venta_granel") in (1, True, "1"))

        if is_granel:
            qty = 1.0
            if hasattr(p, "presentacion_cantidad"):
                qty = float(getattr(p, "presentacion_cantidad") or 1.0)
            if qty > 0:
                final_full = final_full / qty
    except Exception:
        pass

    # Redondeo a 100
    final_full = float(round(final_full, -2))

    # Manual override (Precio manual fijo)
    try:
        man = float(getattr(p, "precio_manual", 0.0) or 0.0)
        if man > 0:
            final_full = man
    except Exception:
        pass

    # Fallback si el precio calculado es 0 (para productos sin lista)
    if final_full == 0:
        for fname in ("precio_minorista", "precio_venta", "precio"):
            try:
                val = float(getattr(p, fname, 0.0) or 0.0)
                if val > 0:
                    final_full = val
                    break
            except Exception:
                pass

    return final_full


def _precio_promo_vigente(session, p: Producto, base_final: float) -> Optional[float]:
    """ Devuelve precio PROMO vigente para p, o None si no hay. """
    if PromocionProducto is None:
        return None
    hoy = date.today()
    pr = (session.query(PromocionProducto)
          .filter(PromocionProducto.producto_id == p.id)
          .filter(PromocionProducto.valor > 0)
          .filter(PromocionProducto.fecha_inicio <= hoy)
          .filter(PromocionProducto.fecha_fin >= hoy)
          .order_by(PromocionProducto.fecha_inicio.desc())
          .first())
    if not pr:
        return None

    try:
        if pr.tipo == "porcentaje":
            pct = max(0.0, min(float(pr.valor or 0.0), 100.0)) / 100.0
            return max(0.0, base_final * (1.0 - pct))
        desc = max(0.0, float(pr.valor or 0.0))
        return max(0.0, base_final - desc)
    except Exception:
        return None


def get_precio_vigente_por_producto(session, p: Producto, params: Dict[str, float] = None) -> Tuple[float, str]:
    """ Retorna (precio_vigente, fuente) donde fuente ∈ {'PROMO','PRECIOS'} """
    if params is None:
        params = calcular_parametros(session)
    base = _precio_final_base(p, params["total_fijos"], params["denom_total"], params["ganancia_pct"])
    promo = _precio_promo_vigente(session, p, base)
    if promo is not None:
        return float(round(promo, 2)), "PROMO"
    return float(round(base, 2)), "PRECIOS"


def get_precio_vigente_por_barcode(session, barcode: str, params: Dict[str, float] = None):
    """ Busca por código de barras y retorna (precio, fuente, producto_id) o None. """
    if not barcode:
        return None
    conds = []
    for cname in ("codigo_barras", "barcode", "cb", "ean", "codigo_barra", "cod_barra"):
        col = getattr(Producto, cname, None)
        if col is not None:
            conds.append(col == barcode)
    if not conds:
        return None

    p = session.query(Producto).filter(or_(*conds)).first()
    if not p:
        return None

    precio, fuente = get_precio_vigente_por_producto(session, p, params)
    return precio, fuente, int(getattr(p, "id", 0))
