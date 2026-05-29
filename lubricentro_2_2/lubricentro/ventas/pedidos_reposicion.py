# -*- coding: utf-8 -*-
"""
ventas/pedidos_reposicion.py
Dispara pedidos automáticos tras cada venta:
- Si el stock de un producto baja del mínimo, agrega una línea a un CSV acumulado.
- Si existe un modelo de 'Pedido'/'Reposicion' en la DB, también intenta insertar.
- No rompe si los modelos no existen.
"""

import os, csv, traceback, datetime as dt
from typing import Optional

from db import SessionLocal, Producto, VentaItem

CSV_DIR = os.path.join("Exports", "Pedidos")
os.makedirs(CSV_DIR, exist_ok=True)

def _log_err(msg: str):
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/errores_BarterPlus.log", "a", encoding="utf-8") as f:
            ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

def _get_stock_min(prod) -> float:
    for campo in ("stock_minimo","min_stock","stock_min","minimo"):
        if hasattr(prod, campo):
            try: return float(getattr(prod, campo) or 0.0)
            except Exception: return 0.0
    return 0.0

def _get_stock_now(prod, session=None) -> float:
    # 1. Intentar usar el hook unificado si está disponible
    try:
        from ventas.stock_hooks import _get_stock_ref
        _, val = _get_stock_ref(prod, session=session)
        if val is not None:
            return float(val)
    except Exception:
        pass

    # 2. Fallback a campos directos
    for campo in ("stock","existencia","cantidad","stock_actual","cant_actual","en_stock"):
        if hasattr(prod, campo):
            try: return float(getattr(prod, campo) or 0.0)
            except Exception: return 0.0
    return 0.0

def _insertar_en_modelo(session, prod, cant_sugerida: float):
    """
    Si existe un modelo de 'Pedido'/'Reposicion' lo usa. Tolerante a esquemas distintos.
    """
    try:
        import db as _db
        candidatos = []
        for name, obj in _db.__dict__.items():
            lname = name.lower()
            if any(k in lname for k in ("pedido","reposic")) and "venta" not in lname:
                candidatos.append(obj)
        if not candidatos:
            return False
        Ped = candidatos[0]
        ped = Ped()
        for f in ("producto_id","id_producto","fk_producto","producto"):
            if hasattr(ped, f):
                try: setattr(ped, f, getattr(prod, "id", None)); break
                except Exception: pass
        for f in ("fecha","created_at","dt","momento"):
            if hasattr(ped, f):
                try: setattr(ped, f, dt.datetime.now()); break
                except Exception: pass
        for f in ("cantidad","cant","q","qty","unidades"):
            if hasattr(ped, f):
                try: setattr(ped, f, float(cant_sugerida)); break
                except Exception: pass
        for f in ("detalle","descripcion","obs","nota","concepto"):
            if hasattr(ped, f):
                try: setattr(ped, f, "Pedido automático por stock mínimo"); break
                except Exception: pass
        session.add(ped)
        return True
    except Exception:
        return False

def _append_csv(prod, cant_sugerida: float):
    ts = dt.datetime.now().strftime("%Y%m%d")
    path = os.path.join(CSV_DIR, f"pedido_auto_{ts}.csv")
    nuevo = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        if nuevo:
            w.writerow(["fecha","producto_id","producto","cant_sugerida"])
        w.writerow([dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    getattr(prod, "id", ""), getattr(prod, "nombre", ""), f"{cant_sugerida:.3f}"])

def evaluar_reposicion_por_venta(venta_id: int):
    """
    Recorre todos los productos vendidos en esa venta y, si están por debajo del mínimo,
    agrega un pedido sugerido (DB si hay modelo, o CSV) y dispara aviso a Proveedores/Pedidos.
    """
    with SessionLocal() as s:
        try:
            # Productos afectados
            try:
                items = s.query(VentaItem).filter(getattr(VentaItem, "venta_id") == int(venta_id)).all()
            except Exception:
                items = [it for it in s.query(VentaItem).all() if getattr(it, "venta_id", None) == int(venta_id)]

            for it in items:
                pid = getattr(it, "producto_id", None)
                if not pid: continue

                # --- Trigger Proveedores/Pedidos logic (REMOVED) ---
                # Ahora se usa escaneo bajo demanda en la pestaña Pedidos
                pass
                # ----------------------------------------------------

                prod = s.query(Producto).get(int(pid))
                if not prod: continue

                stock_min = _get_stock_min(prod)
                if stock_min <= 0:
                    continue
                stock_now = _get_stock_now(prod, session=s)

                if stock_now < stock_min:
                    # Sugerimos reponer hasta mínimo + 20% de colchón
                    sugerida = max(stock_min * 1.2 - stock_now, stock_min - stock_now)
                    ok_db = _insertar_en_modelo(s, prod, sugerida)
                    try:
                        _append_csv(prod, sugerida)
                    except Exception:
                        pass
                    if ok_db:
                        s.commit()
        except Exception:
            s.rollback()
            _log_err("evaluar_reposicion_por_venta error: " + traceback.format_exc())
