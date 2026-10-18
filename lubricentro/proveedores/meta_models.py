# -*- coding: utf-8 -*-
# Metadatos paralelos para proveedores/listas y reglas de precios sin tocar tus modelos.
# - ProveedorMeta: categoría del proveedor (baterias/lubricentro/otro) u otras claves.
# - ListaMeta: metadatos de la lista (tipo_lista, etc.)
# - ReglaPrecio: reglas por (proveedor_id, lista_id opcional, scope, clave) con iva/desc/ajuste.
#   Precedencia en resolución: producto > marca > rubro > proveedor; primero reglas de lista, luego global proveedor.

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, create_engine, Index
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
import datetime as dt

from .bootstrap import bootstrap
_ns = bootstrap()
Engine = _ns.get("engine")
SessionLocal = _ns.get("SessionLocal")
ItemListaProveedor = _ns.get("ItemListaProveedor")

BaseMeta = declarative_base()

class ProveedorMeta(BaseMeta):
    __tablename__ = "proveedor_meta"
    id = Column(Integer, primary_key=True, autoincrement=True)
    proveedor_id = Column(Integer, index=True, nullable=False)
    clave = Column(String(50), nullable=False)
    valor = Column(String(200), nullable=False)

class ListaMeta(BaseMeta):
    __tablename__ = "lista_meta"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lista_id = Column(Integer, index=True, nullable=False)
    clave = Column(String(50), nullable=False)
    valor = Column(String(200), nullable=False)

class ReglaPrecio(BaseMeta):
    __tablename__ = "regla_precio"
    id = Column(Integer, primary_key=True, autoincrement=True)
    proveedor_id = Column(Integer, index=True, nullable=False)
    # lista_id NULL => regla global proveedor; con valor => regla específica de la lista
    lista_id = Column(Integer, index=True, nullable=True)
    # scope: 'proveedor' | 'marca' | 'rubro' | 'producto'
    scope = Column(String(20), index=True, nullable=False)
    # clave: para marca/rubro/producto; para proveedor usar ""
    clave = Column(String(200), index=True, nullable=False, default="")
    iva = Column(Float, nullable=True)      # % (ej 21.0)   None => no aplica
    descuento = Column(Float, nullable=True) # % (ej 10.0)   None => no aplica
    ajuste = Column(Float, nullable=True)   # % (ej 5.0)    None => no aplica
    created_at = Column(DateTime, default=dt.datetime.utcnow)

Index("ix_regla_precio_keys", ReglaPrecio.proveedor_id, ReglaPrecio.lista_id, ReglaPrecio.scope, ReglaPrecio.clave)

def _create_all():
    BaseMeta.metadata.create_all(bind=Engine)
_create_all()

def ensure_precio_original_column():
    """Agrega columna precio_original REAL a ItemListaProveedor si no existe."""
    if not ItemListaProveedor or not Engine:
        return
    table = getattr(ItemListaProveedor, "__tablename__", "item_lista_proveedor")
    with Engine.begin() as conn:
        cols = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        names = {c[1] for c in cols}
        if "precio_original" not in names:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN precio_original REAL"))

# ---------------- helpers metadatos simples ----------------

def set_proveedor_meta(session, proveedor_id: int, clave: str, valor: str):
    session.execute(
        text("DELETE FROM proveedor_meta WHERE proveedor_id=:pid AND clave=:k"),
        dict(pid=proveedor_id, k=clave)
    )
    session.execute(
        text("INSERT INTO proveedor_meta(proveedor_id, clave, valor) VALUES(:pid,:k,:v)"),
        dict(pid=proveedor_id, k=clave, v=str(valor))
    )

def get_proveedor_meta(session, proveedor_id: int, clave: str, default: str = "") -> str:
    row = session.execute(
        text("SELECT valor FROM proveedor_meta WHERE proveedor_id=:pid AND clave=:k LIMIT 1"),
        dict(pid=proveedor_id, k=clave)
    ).fetchone()
    return row[0] if row and len(row) else default

def set_lista_meta(session, lista_id: int, clave: str, valor: str):
    session.execute(
        text("DELETE FROM lista_meta WHERE lista_id=:lid AND clave=:k"),
        dict(lid=lista_id, k=clave)
    )
    session.execute(
        text("INSERT INTO lista_meta(lista_id, clave, valor) VALUES(:lid,:k,:v)"),
        dict(lid=lista_id, k=clave, v=str(valor))
    )

def get_lista_meta(session, lista_id: int, clave: str, default: str = "") -> str:
    row = session.execute(
        text("SELECT valor FROM lista_meta WHERE lista_id=:lid AND clave=:k LIMIT 1"),
        dict(lid=lista_id, k=clave)
    ).fetchone()
    return row[0] if row and len(row) else default

# ---------------- helpers reglas ----------------

def set_regla(session, proveedor_id: int, lista_id, scope: str, clave: str, iva, descuento, ajuste, global_proveedor: bool):
    """Guarda o reemplaza regla. Si global_proveedor=True => lista_id=None (aplica a todas las listas del proveedor)."""
    lid = None if global_proveedor else int(lista_id)
    session.execute(
        text("""DELETE FROM regla_precio WHERE proveedor_id=:pid AND
                (lista_id IS :lid ISNULL OR lista_id=:lid) AND scope=:sc AND clave=:cl""")
        .bindparams(expanding=False),
        dict(pid=proveedor_id, lid=lid, sc=scope, cl=str(clave or ""))
    )
    session.add(ReglaPrecio(
        proveedor_id=int(proveedor_id),
        lista_id=lid,
        scope=scope,
        clave=str(clave or ""),
        iva=None if iva=="" or iva is None else float(iva),
        descuento=None if descuento=="" or descuento is None else float(descuento),
        ajuste=None if ajuste=="" or ajuste is None else float(ajuste),
    ))

def _pick_rule(session, proveedor_id: int, lista_id: int, marca: str, rubro: str, codigo: str):
    """Devuelve (iva, descuento, ajuste, origen) por precedencia:
       Lista: producto>marca>rubro>proveedor; si nada, Global: producto>marca>rubro>proveedor."""
    def _one(lid):
        # producto
        row = session.execute(text("""SELECT iva,descuento,ajuste FROM regla_precio
            WHERE proveedor_id=:pid AND (:lid IS NULL OR lista_id=:lid) AND scope='producto' AND clave=:cl LIMIT 1"""),
            dict(pid=proveedor_id, lid=lid, cl=codigo or "")).fetchone()
        if row: return (row[0], row[1], row[2], ("lista" if lid is not None else "prov") + ":producto")
        # marca
        row = session.execute(text("""SELECT iva,descuento,ajuste FROM regla_precio
            WHERE proveedor_id=:pid AND (:lid IS NULL OR lista_id=:lid) AND scope='marca' AND clave=:cl LIMIT 1"""),
            dict(pid=proveedor_id, lid=lid, cl=(marca or ""))).fetchone()
        if row: return (row[0], row[1], row[2], ("lista" if lid is not None else "prov") + ":marca")
        # rubro
        row = session.execute(text("""SELECT iva,descuento,ajuste FROM regla_precio
            WHERE proveedor_id=:pid AND (:lid IS NULL OR lista_id=:lid) AND scope='rubro' AND clave=:cl LIMIT 1"""),
            dict(pid=proveedor_id, lid=lid, cl=(rubro or ""))).fetchone()
        if row: return (row[0], row[1], row[2], ("lista" if lid is not None else "prov") + ":rubro")
        # proveedor
        row = session.execute(text("""SELECT iva,descuento,ajuste FROM regla_precio
            WHERE proveedor_id=:pid AND (:lid IS NULL OR lista_id=:lid) AND scope='proveedor' AND clave='' LIMIT 1"""),
            dict(pid=proveedor_id, lid=lid)).fetchone()
        if row: return (row[0], row[1], row[2], ("lista" if lid is not None else "prov") + ":proveedor")
        return (None, None, None, "")

    # primero reglas de lista
    iva, dsc, adj, org = _one(lista_id)
    if org:
        return iva, dsc, adj, org
    # luego global proveedor
    iva, dsc, adj, org = _one(None)
    return iva, dsc, adj, org

def aplicar_regla_a_precio(base: float, iva, dsc, adj) -> float:
    """Orden: IVA → Ajuste → Descuento. Cualquier None es 0."""
    iva = 0.0 if iva is None else float(iva)
    dsc = 0.0 if dsc is None else float(dsc)
    adj = 0.0 if adj is None else float(adj)
    precio = float(base or 0.0)
    precio *= (1.0 + iva/100.0)
    precio *= (1.0 + adj/100.0)
    precio *= (1.0 - dsc/100.0)
    return precio

def resolver_para_item(session, proveedor_id: int, lista_id: int, item) -> tuple:
    """Devuelve (precio_base, precio_final, origen_regla, iva, dsc, adj).
       precio_base = precio_original si existe, si no, precio/prec."""
    codigo = getattr(item, "producto_codigo", getattr(item, "codigo", "")) or ""
    marca  = getattr(item, "marca", "") or ""
    rubro  = getattr(item, "rubro_detectado", "") or ""
    base = getattr(item, "precio_original", None)
    if base is None:
        base = getattr(item, "precio", getattr(item, "prec", 0.0))
    iva, dsc, adj, origen = _pick_rule(session, proveedor_id, lista_id, marca, rubro, codigo)
    final = aplicar_regla_a_precio(base, iva, dsc, adj)
    return float(base or 0.0), float(final), origen, iva, dsc, adj
