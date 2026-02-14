import datetime as dt
from typing import Dict, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func, and_

from db import SessionLocal, ConfigParam, Producto, Stock, Deposito

try:
    from productos.precios.bridge_proveedores import min_costo_proveedor_externo
except Exception:
    min_costo_proveedor_externo = None

try:
    from db.models.proveedores import Proveedor, ProveedorPrecio, ItemListaProveedor, ListaPrecioProveedor
except Exception:
    Proveedor = ProveedorPrecio = ItemListaProveedor = ListaPrecioProveedor = None

try:
    from db.models.costos import ImpuestoPeriodo, GastoNegocio, SueldoLiquidacion
except Exception:
    ImpuestoPeriodo = GastoNegocio = SueldoLiquidacion = None

try:
    from db.models.costos_extra import AdelantoSueldo
except Exception:
    AdelantoSueldo = None

try:
    from db.models.productos import PromocionProducto
except Exception:
    PromocionProducto = None

_DEFAULTS = {
    "margen_baterias": "35.0",
    "margen_lubricantes": "35.0",
    "margen_filtros": "35.0",
    "prorrateo_por": "valor",
    "iva_proveedor_default": "21.0",
    "var_cost_total_mensual": "0.0",
}

def _get_param_map() -> Dict[str, str]:
    with SessionLocal() as s:
        vals = {p.clave: p.valor for p in s.query(ConfigParam).all()}
    for k, v in _DEFAULTS.items(): vals.setdefault(k, v)
    return vals

def get_param_float(key: str, default: float) -> float:
    with SessionLocal() as s:
        row = s.query(ConfigParam).filter(ConfigParam.clave == key).first()
        return float(row.valor) if row and row.valor not in (None, "") else float(default)

def set_param(key: str, value: str):
    with SessionLocal() as s:
        row = s.query(ConfigParam).filter(ConfigParam.clave == key).first()
        if row: row.valor = value
        else:   s.add(ConfigParam(clave=key, valor=value))
        s.commit()

def _month_bounds(d: Optional[dt.date] = None) -> Tuple[dt.date, dt.date]:
    d = d or dt.date.today()
    first = dt.date(d.year, d.month, 1)
    nxt = dt.date(d.year + (1 if d.month == 12 else 0), 1 if d.month == 12 else d.month + 1, 1)
    return first, nxt

def total_prorrateable_mes(ref: Optional[dt.date] = None) -> float:
    def _share_by_periodicity(p: Optional[str]) -> int:
        p = (p or "").upper()
        return 1 if p=='MENSUAL' else 2 if p=='BIMESTRAL' else 3 if p=='TRIMESTRAL' else 12 if p=='ANUAL' else 1
    ini, fin = _month_bounds(ref)
    total = 0.0
    with SessionLocal() as s:
        if ImpuestoPeriodo:
            rows = s.query(ImpuestoPeriodo).filter(and_(ImpuestoPeriodo.fecha_inicio < fin, ImpuestoPeriodo.fecha_fin >= ini)).all()
            for r in rows:
                div = _share_by_periodicity(getattr(r, "periodicidad", None))
                total += float(getattr(r, "monto", 0.0) or 0.0) / max(div, 1)
        if GastoNegocio:
            gns = s.query(GastoNegocio).filter(and_(GastoNegocio.fecha >= ini, GastoNegocio.fecha < fin)).all()
            total += sum(float(g.monto or 0.0) for g in gns)
        if SueldoLiquidacion:
            per = f"{ini.year}-{ini.month:02d}"
            sues = s.query(SueldoLiquidacion).filter(SueldoLiquidacion.periodo_label == per).all()
            total += sum(float(su.neto or 0.0) for su in sues)
        if AdelantoSueldo:
            ads = s.query(AdelantoSueldo).filter(and_(AdelantoSueldo.fecha >= ini, AdelantoSueldo.fecha < fin)).all()
            total += sum(float(a.monto or 0.0) for a in ads)
    return float(round(total, 2))

def _min_precio_proveedor(prod: Producto) -> Tuple[Optional[float], Optional[int], Optional[float]]:
    with SessionLocal() as s:
        if ProveedorPrecio:
            row = s.query(ProveedorPrecio).filter(ProveedorPrecio.producto_id == prod.id).order_by(ProveedorPrecio.precio.asc()).first()
            if row:
                return float(row.precio or 0.0), int(row.proveedor_id or 0), float(getattr(row, "iva_pct", 0.0) or 0.0)
        if ItemListaProveedor and ListaPrecioProveedor:
            row2 = s.query(ItemListaProveedor).filter(ItemListaProveedor.producto_id == prod.id).order_by(ItemListaProveedor.precio.asc()).first()
            if row2:
                prov_id = s.query(ListaPrecioProveedor.proveedor_id).filter(ListaPrecioProveedor.id == row2.lista_id).scalar()
                return float(row2.precio or 0.0), int(prov_id or 0), float(getattr(row2, "iva_pct", 0.0) or 0.0)
    if min_costo_proveedor_externo is not None:
        try:
            costo, prov_id, iva_pct = min_costo_proveedor_externo(prod)
            if costo is not None:
                return float(costo), (int(prov_id) if prov_id else 0), float(iva_pct or 0.0)
        except Exception:
            pass
    return None, None, None

def costo_proveedor_iva_descuento(prod: Producto) -> Tuple[float, float, float]:
    precio, prov_id, iva_linea = _min_precio_proveedor(prod)
    if precio is None:
        precio = float(getattr(prod, "costo", 0.0) or 0.0)
    iva_default = get_param_float("iva_proveedor_default", 21.0)
    iva = iva_linea or iva_default
    desc = 0.0
    if Proveedor and prov_id:
        with SessionLocal() as s:
            prov = s.query(Proveedor).get(int(prov_id))
            if prov:
                if not iva_linea:
                    iva = float(getattr(prov, "iva_pct", iva_default) or iva_default)
                desc = float(getattr(prov, "descuento_pct", 0.0) or 0.0)
    return float(precio), float(iva), float(desc)

def mapa_stock_valor(prorrateo_por: Optional[str] = None) -> Dict[int, float]:
    prorrateo_por = (prorrateo_por or _get_param_map()["prorrateo_por"]).strip().lower()
    with SessionLocal() as s:
        agg = dict(s.query(Stock.producto_id, func.sum(Stock.cantidad)).group_by(Stock.producto_id).all())
        productos = s.query(Producto).all()
    base: Dict[int, float] = {}
    for p in productos:
        cant = float(agg.get(p.id, 0.0) or 0.0)
        if prorrateo_por == "cantidad":
            base[p.id] = cant
        else:
            cp, iva, desc = costo_proveedor_iva_descuento(p)
            base_desc = cp * (1 - desc/100.0)
            neto_iva = base_desc / max(1 - iva/100.0, 0.0001)
            base[p.id] = cant * neto_iva
    return base

def prorrateo_cuota(prod: Producto, total_mes: float, base_map: Dict[int, float]) -> float:
    # Prorrateo desactivado por solicitud
    return 0.0
    # base_total = sum(base_map.values()) or 1.0
    # return float(base_map.get(prod.id, 0.0)) / base_total * float(total_mes or 0.0)

def margen_por_rubro(rubro: str) -> Tuple[float, float]:
    m = _get_param_map()
    r = (rubro or "").lower()
    if r.startswith("bater"):
        return float(m["margen_baterias"]), max(float(m["margen_baterias"]) - 10, 0)
    if r.startswith("lubri"):
        return float(m["margen_lubricantes"]), max(float(m["margen_lubricantes"]) - 10, 0)
    if r.startswith("filt"):
        return float(m["margen_filtros"]), max(float(m["margen_filtros"]) - 10, 0)
    return 35.0, 25.0

def promocion_vigente(prod_id: int, fecha: Optional[dt.date] = None):
    if not PromocionProducto: return None
    fecha = fecha or dt.date.today()
    with SessionLocal() as s:
        return (s.query(PromocionProducto)
                .filter(PromocionProducto.producto_id == prod_id,
                        PromocionProducto.activo == True,
                        PromocionProducto.fecha_inicio <= fecha,
                        PromocionProducto.fecha_fin >= fecha)
                .order_by(PromocionProducto.fecha_inicio.desc())
                .first())

def _round2(v: float) -> float:
    return float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def precio_final_sugerido(prod: Producto, total_prorrateable: Optional[float] = None, base_map: Optional[Dict[int, float]] = None) -> Tuple[float, float]:
    cp, iva_pct, desc_pct = costo_proveedor_iva_descuento(prod)
    if total_prorrateable is None:
        total_prorrateable = total_prorrateable_mes()
    if base_map is None:
        base_map = mapa_stock_valor()
    pro = prorrateo_cuota(prod, total_prorrateable, base_map)
    gan, _ = margen_por_rubro(prod.rubro or "")
    A = max(desc_pct, 0.0) / 100.0
    B = max(iva_pct, 0.0) / 100.0
    C = max(float(gan or 0.0), 0.0) / 100.0
    base_desc = cp - (cp * A)
    neto_iva = base_desc / max(1.0 - B, 0.0001)
    pf = (neto_iva + pro) / max(1.0 - C, 0.0001)

    # Redondeo base a 100
    pf = float(round(pf, -2))

    # Override manual
    try:
        man = float(getattr(prod, "precio_manual", 0.0) or 0.0)
        if man > 0:
            pf = man
    except Exception:
        pass

    promo = promocion_vigente(prod.id)
    if promo:
        t = (getattr(promo, "tipo", "fijo") or "fijo").strip().lower()
        v = float(getattr(promo, "valor", 0.0) or 0.0)
        if t == "fijo": pf = v
        elif t == "porcentaje": pf = pf * (1.0 - max(0.0, min(v, 100.0)) / 100.0)
    pf = _round2(pf)
    return pf, pf