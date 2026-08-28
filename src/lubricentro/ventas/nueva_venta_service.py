# -*- coding: utf-8 -*-
"""
ventas/nueva_venta_service.py
Lógica de ventas desacoplada de la UI.
"""

import os, re, traceback, datetime as dt
from typing import List, Tuple, Dict, Any, Optional

from PyQt5.QtWidgets import QMessageBox

from db import SessionLocal, Cliente, Producto, Venta, VentaItem
try:
    from db import VentaPago
except Exception:
    VentaPago = None

from services.config_service import ConfigService

# Hooks de stock / reposición
try:
    from ventas.stock_hooks import _normalizar_cantidad, descontar_stock_por_venta, revertir_stock_por_venta
except Exception:
    def _normalizar_cantidad(session, producto_id, cantidad_raw):
        try:
            txt = str(cantidad_raw).strip().lower().replace(",", ".")
            return float(re.sub(r"[^0-9\.]", "", txt) or 0.0), "Unid"
        except Exception:
            return 0.0, "Unid"
    def descontar_stock_por_venta(venta_id, deposito_id_preferido=1): pass
    def revertir_stock_por_venta(venta_id): pass

try:
    from ventas.pedidos_reposicion import evaluar_reposicion_por_venta
except Exception:
    def evaluar_reposicion_por_venta(_): pass

# Diálogo de consulta de precios
from ventas.consultar_precio_dialog import ConsultarPrecioDialog

# Búsqueda y precio vigente (lazy import para evitar ciclos)
# Se importarán localmente en los métodos que lo requieran
pass


# ------- utilidades -------
def fmt_money(v: float) -> str:
    try:
        return f"${float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "$0,00"

def log_err(msg: str):
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/errores_BarterPlus.log", "a", encoding="utf-8") as f:
            ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


# ------- cuentas corrientes (modelo flexible) -------
import inspect as _inspect
def _discover_cc_models():
    modelos = []
    try:
        import db as _db
        for name, obj in _db.__dict__.items():
            if not _inspect.isclass(obj): continue
            lname = name.lower()
            if ("cta" in lname or "corrient" in lname) and name not in ("Cliente",):
                modelos.append(obj)
    except Exception:
        pass
    return modelos

def _impactar_cta_cte(session, cli, venta, monto_cc: float, detalle: str = ""):
    modelos = _discover_cc_models()
    if not modelos or not cli or monto_cc <= 0:
        return
    mov_model = modelos[0]
    try:
        mov = mov_model()
    except Exception:
        return

    for campo in ("cliente_id","id_cliente","fk_cliente","cliente"):
        if hasattr(mov, campo):
            try: setattr(mov, campo, getattr(cli, "id", None)); break
            except Exception: pass

    for campo in ("fecha","fch","created_at","dt","fecha_mov"):
        if hasattr(mov, campo):
            try: setattr(mov, campo, getattr(venta, "fecha", dt.datetime.now())); break
            except Exception: pass

    for campo in ("venta_id","id_venta","fk_venta","venta"):
        if hasattr(mov, campo):
            try: setattr(mov, campo, int(getattr(venta, "id"))); break
            except Exception: pass
    for campo in ("comprobante","nro_comprobante","numero","nro"):
        if hasattr(mov, campo) and hasattr(venta, campo):
            try: setattr(mov, campo, getattr(venta, campo)); break
            except Exception: pass

    txt = "Venta a Cuenta Corriente"
    if detalle: txt += f" — {detalle}"
    for campo in ("detalle","descripcion","observacion","concepto","nota"):
        if hasattr(mov, campo):
            try: setattr(mov, campo, txt); break
            except Exception: pass

    if hasattr(mov, "debe") or hasattr(mov, "haber"):
        try:
            if hasattr(mov, "debe"): mov.debe = float(monto_cc)
            if hasattr(mov, "haber"): mov.haber = 0.0
        except Exception:
            pass
    else:
        for campo in ("monto","importe","valor","total"):
            if hasattr(mov, campo):
                try: setattr(mov, campo, float(monto_cc)); break
                except Exception: pass

    try:
        session.add(mov)
    except Exception:
        pass


# ------- service -------
class NuevaVentaService:
    """
    Se usa desde la UI. Mantiene items y pagos en memoria y expone operaciones.
    """
    def __init__(self):
        self.items: List[Tuple[Optional[int], str, float, float]] = []  # (producto_id, nombre, cant_norm, subtotal_bruto)
        self.pagos_doc: List[Tuple[str, float, str]] = []              # (medio, monto, detalle)
        self._tarj_cfg_cache = None
        self.descuento_global = 0.0
        self.observacion_descuento = ""

    def set_descuento_global(self, monto, obs):
        self.descuento_global = max(0.0, float(monto or 0.0))
        self.observacion_descuento = (obs or "").strip()

    @property
    def tarj_cfg(self):
        if self._tarj_cfg_cache is None:
            with SessionLocal() as s:
                self._tarj_cfg_cache = ConfigService.get_tarjeta_coefs(s)
        return self._tarj_cfg_cache

    # ----- clientes -----
    def find_cliente_by_id(self, cid: Optional[int]):
        if not cid:
            return None
        with SessionLocal() as s:
            try:
                return s.query(Cliente).get(int(cid))
            except Exception:
                return None

    def find_cliente(self, texto: str):
        with SessionLocal() as s:
            t = (texto or "").strip()
            if not t:
                return None
            c = s.query(Cliente).filter(Cliente.cuit_dni == t).first()
            if c: return c
            c = s.query(Cliente).filter(Cliente.nombre == t).first()
            if c: return c
            try:
                from sqlalchemy import func
                tlike = f"%{t}%"
                return s.query(Cliente).filter(func.lower(Cliente.nombre).like(func.lower(tlike))).first()
            except Exception:
                return None

    def cliente_especial(self, cli) -> bool:
        if cli is None: return False
        for n in ("especial","es_especial","cliente_especial","vip","is_special"):
            if hasattr(cli, n) and bool(getattr(cli, n)): return True
        for n in ("tipo_cliente","categoria","tipo"):
            if hasattr(cli, n) and str(getattr(cli, n) or "").lower().startswith("esp"):
                return True
        for n in ("descuento","descuento_pct","porcentaje_descuento"):
            if hasattr(cli, n):
                try:
                    if float(getattr(cli, n) or 0) >= 9.9: return True
                except Exception:
                    pass
        return False

    # ----- tarjetas -----
    def recargo_tarjeta(self, marca: str, cuotas: int) -> float:
        try:
            return float(self.tarj_cfg.get(str(marca), {}).get(int(cuotas), 0.0))
        except Exception:
            return 0.0

    # ----- productos / precios -----
    def _precio_por_producto(self, s, prod) -> float:
        from ventas.precio_busquedas import precio_vigente, calcular_parametros
        try:
            params = calcular_parametros(s)
        except Exception:
            params = None
        try:
            return float(precio_vigente(s, prod, params) or 0.0)
        except Exception:
            return 0.0

    def resolver_producto_y_precio(self, token: str) -> Tuple[Optional[int], str, float]:
        from ventas.precio_busquedas import find_producto_robusto
        with SessionLocal() as s:
            p = find_producto_robusto(s, (token or "").strip())
            if not p:
                return None, (token or "").strip(), 0.0
            pid = getattr(p, "id", None)
            nombre = getattr(p, "nombre", token)
            prec = self._precio_por_producto(s, p)
            return pid, nombre, prec

    def resolver_producto_por_id(self, pid: int) -> Tuple[str, float]:
        with SessionLocal() as s:
            p = s.query(Producto).get(int(pid))
            if not p:
                return "", 0.0
            return getattr(p, "nombre", f"Producto {pid}"), self._precio_por_producto(s, p)

    def es_producto_granel(self, pid: int) -> Tuple[bool, float, str]:
        """
        Retorna (es_granel, presentacion_cantidad, presentacion_unidad)
        """
        if not pid: return False, 1.0, "Unidad"
        with SessionLocal() as s:
            p = s.query(Producto).get(int(pid))
            if not p: return False, 1.0, "Unidad"
            # Detectar si es granel por flag venta_granel (si existe) o heurística
            es_granel = False
            if hasattr(p, "venta_granel") and p.venta_granel:
                es_granel = True

            cant = 1.0
            unidad = "Unidad"
            if hasattr(p, "presentacion_cantidad"):
                try: cant = float(p.presentacion_cantidad or 1.0)
                except: cant = 1.0
            if hasattr(p, "presentacion_unidad"):
                unidad = str(p.presentacion_unidad or "Unidad")
            return es_granel, cant, unidad

    def normalizar_cantidad(self, producto_id: int, texto_cantidad: str) -> Tuple[float, str]:
        with SessionLocal() as s:
            return _normalizar_cantidad(s, int(producto_id), texto_cantidad or "1")

    # ----- items en memoria -----
    def add_item(self, producto_id: Optional[int], nombre: str, cant_norm: float, precio_unit: float):
        self.items.append((producto_id, nombre, float(cant_norm), float(cant_norm) * float(precio_unit)))

    def update_item_subtotal(self, index: int, new_subtotal: float):
        if 0 <= index < len(self.items):
            pid, nombre, cant, _old_sub = self.items[index]
            self.items[index] = (pid, nombre, cant, float(new_subtotal))

    def remove_item(self, index: int):
        if 0 <= index < len(self.items):
            self.items.pop(index)

    def clear_items(self):
        self.items.clear()
        self.descuento_global = 0.0
        self.observacion_descuento = ""

    # ----- totales -----
    def total_items(self) -> float:
        return sum(float(sub) for _pid,_n,_c,sub in self.items)

    def total_con_desc(self, es_especial: bool) -> float:
        desc = 10.0 if es_especial else 0.0
        base = self.total_items() * (1 - desc/100.0)
        # Apply global discount
        return max(0.0, base - self.descuento_global)

    def total_tarjeta(self, base: float, marca: str, cuotas: int) -> Tuple[float, float]:
        rec = self.recargo_tarjeta(marca, cuotas)
        tot = base * (1 + rec/100.0)
        return tot, (tot / max(int(cuotas or 1), 1))

    # ----- pagos en memoria -----
    def set_pagos(self, pagos: List[Tuple[str, float, str]]):
        self.pagos_doc = list(pagos or [])

    # ----- comprobante -----
    def _next_comprobante(self, s, venta_model: Venta) -> str:
        pv = 1
        for f in ("punto_venta","pto_venta","pv"):
            if hasattr(venta_model, f):
                try:
                    pv = int(getattr(venta_model, f) or 1); break
                except Exception: pass
        pv = max(1, pv)
        max_seq = 0
        try:
            rows = s.query(venta_model).all()
        except Exception:
            rows = []
        for v in rows:
            seq = 0; pv_old = pv
            for f in ("comprobante","nro_comprobante","numero","nro"):
                if hasattr(v, f):
                    try:
                        raw = str(getattr(v, f) or "")
                        m = re.search(r"(\d{4})-(\d{6})", raw)
                        if m: pv_old = int(m.group(1)); seq = int(m.group(2))
                        else: seq = int(raw)
                    except Exception:
                        pass
            if pv_old == pv and seq > max_seq:
                max_seq = seq
        return f"{pv:04d}-{(max_seq+1):06d}"

    # ----- guardar venta -----
    def guardar_venta(self, cliente_txt: str, es_especial: bool,
                      forma_pago: str, tarjeta_info: Dict[str, Any]) -> Dict[str, Any]:
        if not self.items:
            raise RuntimeError("No hay ítems")

        base = self.total_con_desc(es_especial)
        pagos_doc: List[Tuple[str,float,str]] = []

        if forma_pago == "Tarjeta":
            marca = str(tarjeta_info.get("marca",""))
            cuotas = int(tarjeta_info.get("cuotas") or 1)
            total, _cuota = self.total_tarjeta(base, marca, cuotas)
            det = " ".join(x for x in [("Lote "+tarjeta_info.get("lote","")) if tarjeta_info.get("lote") else "",
                                       ("Cupón "+tarjeta_info.get("cupon","")) if tarjeta_info.get("cupon") else ""] if x).strip()
            pagos_doc = [(f"Tarjeta {marca} x{cuotas}", float(total), det)]
        elif forma_pago == "Débito":
            marca = str(tarjeta_info.get("marca",""))
            det = " ".join(x for x in [("Lote "+tarjeta_info.get("lote","")) if tarjeta_info.get("lote") else "",
                                       ("Cupón "+tarjeta_info.get("cupon","")) if tarjeta_info.get("cupon") else ""] if x).strip()
            pagos_doc = [(f"Débito {marca}", float(base), det)]
        elif forma_pago.lower().startswith("cuenta corr"):
            pagos_doc = [("Cuenta Corriente", float(base), "CC")]
        elif forma_pago == "Combinada":
            pagos_doc = list(self.pagos_doc or [])
            if not pagos_doc:
                raise RuntimeError("Pagos combinados vacíos")
            try:
                base = sum(float(p[1]) for p in pagos_doc)
            except Exception:
                pass
        else:
            pagos_doc = [(forma_pago, float(base), "")]

        with SessionLocal() as s:
            venta = Venta()
            for k in ("fecha","created_at","dt","momento"):
                if hasattr(venta, k):
                    try: setattr(venta, k, dt.datetime.now())
                    except Exception: pass
            nro = self._next_comprobante(s, Venta)
            for f in ("comprobante","nro_comprobante","numero","nro"):
                if hasattr(venta, f):
                    try: setattr(venta, f, nro)
                    except Exception: pass

            cli = self.find_cliente(cliente_txt)
            if hasattr(venta, "cliente_id") and cli is not None:
                try: venta.cliente_id = cli.id
                except Exception: pass
            for attr in ("cliente_nombre","nombre_cliente","cliente_texto","cliente_str"):
                if hasattr(venta, attr):
                    try: setattr(venta, attr, (getattr(cli, "nombre", "") or cliente_txt).strip()); break
                    except Exception: pass

            for k in ("total","total_final","importe_total","monto_total","importe","monto"):
                if hasattr(venta, k):
                    try: setattr(venta, k, float(base))
                    except Exception: pass

            # Save discount if present
            if hasattr(venta, "descuento"):
                venta.descuento = self.descuento_global
            if hasattr(venta, "motivo_descuento"):
                venta.motivo_descuento = self.observacion_descuento

            # Also append to observations
            if self.descuento_global > 0:
                obs_txt = f"Descuento: ${self.descuento_global:.2f} ({self.observacion_descuento})"
                if hasattr(venta, "observaciones"):
                    curr = (getattr(venta, "observaciones") or "")
                    venta.observaciones = (curr + " | " + obs_txt).strip(" | ")

            s.add(venta); s.flush()

            items_planos = []
            for pid, nombre, cant, sub_br in self.items:
                q = float(cant or 0.0)
                sub_fin = float(sub_br) * (1 - (10.0 if es_especial else 0.0)/100.0)
                it = VentaItem()
                if hasattr(it, "venta_id"): it.venta_id = venta.id
                if hasattr(it, "producto_id") and pid: it.producto_id = int(pid)
                for f in ("nombre","descripcion","detalle","texto"):
                    if hasattr(it, f):
                        try: setattr(it, f, nombre); break
                        except Exception: pass
                for f in ("cantidad","cant","q","qty","unidades"):
                    if hasattr(it, f):
                        try: setattr(it, f, q); break
                        except Exception: pass
                seteado = False
                for f in ("precio","precio_unit","precio_unitario","p_unit","precio_venta",
                          "precio_u","unit_price","valor_unitario","importe_unit"):
                    if hasattr(it, f):
                        try: setattr(it, f, float(sub_fin) / max(q, 1)); seteado = True; break
                        except Exception: pass
                if not seteado:
                    for f in ("precio_bruto","precio_lista","p_unit_bruto","precio_sin_desc"):
                        if hasattr(it, f):
                            try: setattr(it, f, float(sub_br) / max(q, 1)); break
                            except Exception: pass
                for f in ("subtotal","importe","total","valor"):
                    if hasattr(it, f):
                        try: setattr(it, f, float(sub_fin)); break
                        except Exception: pass
                s.add(it)
                items_planos.append({"nombre": nombre, "cant": q, "subtotal": sub_fin})

            if VentaPago and pagos_doc:
                for p in pagos_doc:
                    try:
                        medio, monto = p[0], float(p[1] or 0.0)
                        det = p[2] if len(p) > 2 else ""
                        vp = VentaPago()
                        for k in ("medio","forma","tipo","forma_pago","metodo","medio_pago"):
                            if hasattr(vp, k): setattr(vp, k, medio); break
                        for k in ("monto","importe","valor","total"):
                            if hasattr(vp, k): setattr(vp, k, monto); break
                        for k in ("detalle","observacion","obs","nota","info"):
                            if hasattr(vp, k): setattr(vp, k, det); break
                        for k in ("venta_id","id_venta","fk_venta","venta"):
                            if hasattr(vp, k): setattr(vp, k, int(venta.id)); break
                        s.add(vp)
                    except Exception:
                        s.rollback()

            if any("cuenta corr" in (p[0].lower()) for p in pagos_doc):
                try:
                    _impactar_cta_cte(s, cli, venta, float(base), detalle=f"Comprobante {nro}")
                except Exception:
                    log_err("Impacto CC error: " + traceback.format_exc())

            s.commit()
            venta_id = int(getattr(venta, "id"))

        try:
            descontar_stock_por_venta(venta_id, deposito_id_preferido=1)
        except Exception:
            log_err("descontar_stock_por_venta error: " + traceback.format_exc())
        try:
            evaluar_reposicion_por_venta(venta_id)
        except Exception:
            log_err("evaluar_reposicion_por_venta error: " + traceback.format_exc())

        return {
            "venta_id": venta_id, "total": float(base),
            "fecha": dt.datetime.now(), "cliente": (cliente_txt or "").strip(),
            "comprobante": nro, "items_planos": items_planos, "pagos_doc": pagos_doc
        }

    # ----- buscar venta -----
    def buscar_venta_flexible(self, input_str: str):
        """
        Busca venta por ID o por comprobante (ej: 123 -> 0001-000123).
        Retorna dict con datos para confirmación o None.
        """
        input_str = (input_str or "").strip()
        if not input_str:
            return None

        with SessionLocal() as s:
            # 1. Por ID directo
            if input_str.isdigit():
                v = s.query(Venta).get(int(input_str))
                if v: return self._data_venta(v)

            # 2. Por comprobante (si existe col) o numero
            col_comp = getattr(Venta, "comprobante", None)
            if col_comp:
                v = s.query(Venta).filter(col_comp == input_str).first()
                if v: return self._data_venta(v)

            # 3. Por número (si el input es parseable a int o formato XXX-YYY)
            # Input: "123" -> numero=123
            # Input: "0001-000123" -> numero=123 (asumiendo que numero guarda el secuencial)
            try:
                num_busq = -1
                if input_str.isdigit():
                    num_busq = int(input_str)
                elif "-" in input_str:
                    parts = input_str.split("-")
                    if len(parts) == 2 and parts[1].isdigit():
                        num_busq = int(parts[1])

                if num_busq > 0:
                    # Intentar buscar por 'numero' o 'nro'
                    col_nro = getattr(Venta, "numero", None) or getattr(Venta, "nro", None)
                    if col_nro:
                        v = s.query(Venta).filter(col_nro == num_busq).first()
                        if v: return self._data_venta(v)
            except Exception:
                pass

            return None

    def _data_venta(self, v):
        # Helper para extraer datos de confirmación
        comp = getattr(v, "comprobante", "") or getattr(v, "nro_comprobante", "") or str(v.id)
        fecha = getattr(v, "fecha", "")
        if isinstance(fecha, dt.datetime): fecha = fecha.strftime("%d/%m/%Y %H:%M")

        # Cliente
        cli = getattr(v, "cliente_nombre", "") or ""
        if not cli and getattr(v, "cliente", None):
            cli = v.cliente.nombre

        total = getattr(v, "total", 0.0) or 0.0

        estado = "Emitida"
        if getattr(v, "anulada", False): estado = "ANULADA"
        elif str(getattr(v, "estado", "")).upper() == "ANULADA": estado = "ANULADA"

        return {
            "id": v.id,
            "comprobante": comp,
            "fecha": fecha,
            "cliente": cli,
            "total": total,
            "estado": estado
        }

    # ----- anular venta -----
    def anular_venta(self, venta_id: int):
        with SessionLocal() as s:
            try:
                v = s.query(Venta).get(int(venta_id))
                if not v:
                    raise RuntimeError(f"Venta {venta_id} no encontrada")

                # Check idempotency
                ya_anulada = False
                if hasattr(v, "anulada") and v.anulada: ya_anulada = True
                if hasattr(v, "estado") and str(v.estado).upper() == "ANULADA": ya_anulada = True

                if ya_anulada:
                    raise RuntimeError(f"La venta {venta_id} ya está anulada.")

                # Set annulled
                if hasattr(v, "estado"):
                    v.estado = "ANULADA"
                if hasattr(v, "anulada"):
                    v.anulada = True

                # Add note if possible
                if hasattr(v, "observacion"):
                    obs = (getattr(v, "observacion") or "").strip()
                    obs = (obs + " | " if obs else "") + f"Anulada {dt.datetime.now():%Y-%m-%d %H:%M}"
                    v.observacion = obs

                s.commit()
            except Exception:
                s.rollback()
                raise

        try:
            revertir_stock_por_venta(int(venta_id))
        except Exception:
            log_err("revertir_stock_por_venta error: " + traceback.format_exc())
            raise

    # ----- consultar precio -----
    def consultar_precio(self, parent, token_inicial: str = ""):
        if ConsultarPrecioDialog is None:
            QMessageBox.warning(parent, "Consulta de precios", "Módulo de diálogo no disponible.")
            return
        dlg = ConsultarPrecioDialog(parent, token_inicial=(token_inicial or "").strip())
        # intentar disparar búsqueda automática si el diálogo lo soporta
        for m in ("buscar", "do_search", "on_buscar", "exec_search"):
            if hasattr(dlg, m) and callable(getattr(dlg, m)):
                try:
                    getattr(dlg, m)()
                except Exception:
                    pass
                break
        dlg.exec_()
        return getattr(dlg, "selected_data", None)
