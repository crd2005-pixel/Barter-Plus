# -*- coding: utf-8 -*-
"""
ventas/stock_hooks.py
- Normaliza cantidades ingresadas (ml/L, g/Kg, unidades).
- Descuenta stock por venta (robusto a distintos nombres de campos).
- Revertir stock si se anula la venta.
Reglas:
- Siempre usar context managers (with SessionLocal()).
- No asume columnas fijas: prueba múltiples nombres comunes.
- Si existe tabla de movimientos de stock, intenta registrarla.
- Loggea errores a logs/errores_BarterPlus.log
"""

import os, re, traceback
import datetime as dt
from typing import Tuple, Optional

from db import SessionLocal, Venta, VentaItem, Producto

# -------- utilidades de log --------
def _log_err(msg: str):
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/errores_BarterPlus.log", "a", encoding="utf-8") as f:
            ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


# -------- normalización de cantidad --------
_UNIDADES = {
    # clave en texto -> (factor_a_unidad_base, unidad_base)
    # líquidos: base = Litro
    r"(ml|cc)$": (1.0/1000.0, "L"),
    r"(l|litro|litros)$": (1.0, "L"),
    # sólidos: base = Kg
    r"(g|gramo|gramos)$": (1.0/1000.0, "Kg"),
    r"(kg|kilo|kilos)$": (1.0, "Kg"),
    # unidades
    r"(u|unid|unidad|unidades)$": (1.0, "Unid"),
}

def _detectar_unidad(texto: str) -> Tuple[float, str]:
    t = (texto or "").strip().lower()
    for pat, (factor, base) in _UNIDADES.items():
        if re.search(pat, t):
            return factor, base
    # si no detecta terminación, intenta heurística por separadores
    if re.search(r"[0-9]\s*(ml|cc)", t):   return 1.0/1000.0, "L"
    if re.search(r"[0-9]\s*(g)", t):       return 1.0/1000.0, "Kg"
    if re.search(r"[0-9]\s*(kg)", t):      return 1.0, "Kg"
    if re.search(r"[0-9]\s*(l)", t):       return 1.0, "L"
    return 1.0, "Unid"

def _parse_valor(texto: str) -> float:
    # Acepta "0,5", "0.5", "250 ml", etc.
    s = (texto or "").strip().lower().replace(",", ".")
    nums = re.findall(r"[0-9]*\.?[0-9]+", s)
    return float(nums[-1]) if nums else 0.0

def _unidad_base_producto(prod) -> str:
    # Si en la DB hay pistas, usarlas
    for campo in ("unidad_base","unidad","presentacion","u_base","uventa","unidad_venta"):
        if hasattr(prod, campo):
            try:
                val = str(getattr(prod, campo) or "").strip()
                if val:
                    v = val.lower()
                    if v.startswith(("l","ml","cc")): return "L"
                    if v.startswith(("kg","g")):       return "Kg"
                    return "Unid"
            except Exception:
                pass
    return "Unid"

def _normalizar_a_base(prod, valor: float, base_detectada: str) -> Tuple[float, str]:
    base_prod = _unidad_base_producto(prod)
    if base_prod == "L":
        if base_detectada == "L":  return valor, "L"
        if base_detectada == "Kg": return valor, "L"  # preferimos no convertir densidades
        return valor, "L"
    if base_prod == "Kg":
        if base_detectada == "Kg": return valor, "Kg"
        if base_detectada == "L":  return valor, "Kg"
        return valor, "Kg"
    # Unidades
    return valor, "Unid"

def _leer_qty_item(it) -> float:
    for f in ("cantidad","cant","q","qty","unidades"):
        if hasattr(it, f):
            try: return float(getattr(it, f) or 0.0)
            except Exception: pass
    return 0.0

def _get_stock_ref(prod, session=None):
    """
    Devuelve (nombre_de_campo_stock, valor_actual) si encuentra alguno.
    Soporte extendido para tabla 'Stock' relacionada.
    """
    # 1. Buscar en el objeto Producto (campos directos)
    for campo in ("stock","existencia","cantidad","stock_actual","cant_actual","en_stock"):
        if hasattr(prod, campo):
            try:
                return campo, float(getattr(prod, campo) or 0.0)
            except Exception:
                return campo, 0.0

    # 2. Buscar en tabla Stock relacionada (si session está disponible)
    if session:
        try:
            # Intentar importar modelo Stock
            # Esto asume que db.models.productos.Stock existe y tiene producto_id
            from db.models.productos import Stock
            st = session.query(Stock).filter(Stock.producto_id == prod.id).first()
            if st:
                return "relation_Stock", float(st.cantidad or 0.0)
        except Exception:
            pass

    return None, None

def _set_stock(prod, nuevo_valor: float, session=None):
    # 1. Intentar actualizar en campo directo del Producto
    updated = False
    for campo in ("stock","existencia","cantidad","stock_actual","cant_actual","en_stock"):
        if hasattr(prod, campo):
            try:
                setattr(prod, campo, float(nuevo_valor))
                updated = True
            except Exception:
                pass

    if updated:
        return True

    # 2. Intentar actualizar en tabla Stock relacionada
    if session:
        try:
            from db.models.productos import Stock
            st = session.query(Stock).filter(Stock.producto_id == prod.id).first()
            if st:
                st.cantidad = float(nuevo_valor)
                return True
            else:
                # Crear si no existe (asumiendo deposito_id=1 por defecto)
                new_st = Stock(producto_id=prod.id, deposito_id=1, cantidad=float(nuevo_valor))
                session.add(new_st)
                return True
        except Exception:
            pass

    return False


# -------- API pública --------
def _normalizar_cantidad(session, producto_id: int, cantidad_raw) -> Tuple[float, str]:
    """
    Recibe el texto tal como lo ingresa el usuario (e.g., '250ml', '0,5 l', '300 g', '2').
    Devuelve (cantidad_en_unidad_base_del_producto, unidad_base_str).
    """
    try:
        prod = session.get(Producto, int(producto_id))
    except Exception:
        prod = None

    txt = str(cantidad_raw or "").strip()
    val = _parse_valor(txt)
    factor, base_detectada = _detectar_unidad(txt)
    cant = val * factor

    if prod is None:
        # sin producto, no sabemos la base → asumimos Unid
        return cant, "Unid"

    cant_conv, base_final = _normalizar_a_base(prod, cant, base_detectada)
    return float(cant_conv), base_final


def descontar_stock_por_venta(venta_id: int, deposito_id_preferido: int = 1):
    """
    Descuenta stock de los productos involucrados en la venta.
    - Busca VentaItem por venta_id
    - Toma 'cantidad' (o alias)
    - Resta a campo de stock disponible
    """
    with SessionLocal() as s:
        try:
            venta = s.get(Venta, int(venta_id))
            if not venta:
                return False

            # ítems
            try:
                items = s.query(VentaItem).filter(
                    getattr(VentaItem, "venta_id") == int(venta_id)
                ).all()
            except Exception:
                # si el modelo difiere, mejor traer todo y filtrar a mano
                items = [it for it in s.query(VentaItem).all() if getattr(it, "venta_id", None) == int(venta_id)]

            for it in items:
                pid = getattr(it, "producto_id", None)
                if not pid:
                    continue
                prod = s.get(Producto, int(pid))
                if not prod:
                    continue

                q = _leer_qty_item(it)
                # si el ítem se guardó ya normalizado, usarlo; si no, intentar normalizar
                if q <= 0:
                    q = 0.0
                # restar
                campo, stock_actual = _get_stock_ref(prod, session=s)
                if campo is None:
                    # Si no se encuentra stock, intentar crearlo en 0 para poder restar? No, mejor logear.
                    _log_err(f"Venta {venta_id}: Producto {prod.id} no tiene campo de stock ni tabla Stock relacionada.")
                    # Intentamos forzar la creación de entrada en tabla Stock
                    _set_stock(prod, -float(q), session=s)
                    continue

                nuevo = float(stock_actual or 0.0) - float(q)
                _set_stock(prod, nuevo, session=s)

                # opcional: registrar movimiento si existe tabla
                _registrar_movimiento_stock(s, prod, -abs(q), motivo=f"Venta {venta_id}")

            s.commit()

            return True
        except Exception:
            s.rollback()
            _log_err("descontar_stock_por_venta error: " + traceback.format_exc())
            return False


def revertir_stock_por_venta(venta_id: int):
    """
    Recompone el stock sumando las cantidades de la venta indicada.
    Pensado para usar al ANULAR una venta.
    """
    with SessionLocal() as s:
        try:
            venta = s.get(Venta, int(venta_id))
            if not venta:
                return False

            try:
                items = s.query(VentaItem).filter(
                    getattr(VentaItem, "venta_id") == int(venta_id)
                ).all()
            except Exception:
                items = [it for it in s.query(VentaItem).all() if getattr(it, "venta_id", None) == int(venta_id)]

            for it in items:
                pid = getattr(it, "producto_id", None)
                if not pid:
                    continue
                prod = s.get(Producto, int(pid))
                if not prod:
                    continue

                q = _leer_qty_item(it)
                if q <= 0:
                    q = 0.0
                campo, stock_actual = _get_stock_ref(prod, session=s)
                if campo is None:
                    continue
                nuevo = float(stock_actual or 0.0) + float(q)
                _set_stock(prod, nuevo, session=s)

                _registrar_movimiento_stock(s, prod, +abs(q), motivo=f"Anulación venta {venta_id}")

            s.commit()
            return True
        except Exception:
            s.rollback()
            _log_err("revertir_stock_por_venta error: " + traceback.format_exc())
            return False


# -------- soporte a movimientos si existiera algún modelo --------
def _registrar_movimiento_stock(session, prod, cantidad: float, motivo: str = ""):
    """
    Intenta detectar un modelo de movimientos de stock y registrar. Si no hay, no hace nada.
    Busca por nombres típicos: 'StockMov', 'MovimientoStock', 'Kardex', etc.
    """
    try:
        import db as _db
        candidatos = []
        for name, obj in _db.__dict__.items():
            try:
                if name.lower() in ("stockmov","movimientostock","stockmovimiento","kardex","movstock","stock_kardex"):
                    candidatos.append(obj)
            except Exception:
                pass
        if not candidatos:
            return
        Mov = candidatos[0]
        mov = Mov()
        for f in ("producto_id","id_producto","fk_producto","producto"):
            if hasattr(mov, f):
                try: setattr(mov, f, getattr(prod, "id", None)); break
                except Exception: pass
        for f in ("fecha","created_at","dt","momento"):
            if hasattr(mov, f):
                try: setattr(mov, f, dt.datetime.now()); break
                except Exception: pass
        for f in ("cantidad","cant","q","qty","unidades"):
            if hasattr(mov, f):
                try: setattr(mov, f, float(cantidad)); break
                except Exception: pass
        for f in ("detalle","motivo","descripcion","obs","concepto"):
            if hasattr(mov, f):
                try: setattr(mov, f, str(motivo)); break
                except Exception: pass
        session.add(mov)
    except Exception:
        # silencioso: es opcional
        pass
