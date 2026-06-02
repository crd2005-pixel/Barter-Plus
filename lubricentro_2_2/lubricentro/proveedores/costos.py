# -*- coding: utf-8 -*-
"""
proveedores/costos.py

Persistencia de porcentajes y cálculos para listas y marcas.
- % por LISTA (desc, iva) con UPSERT.
- % por MARCA dentro de una lista (desc, iva) con UPSERT.
- Cálculo centralizado (tus fórmulas).
- Compatibilidad SQLAlchemy 1.4/2.0 (session.execute(text(...))).
- NORMALIZACIÓN DE MARCA: trim, colapsar espacios, sin acentos, MAYÚSCULAS.
  Esto asegura que "acdelco", "ACDelco", "ACDELCO" y "  A C D e l c o  " sean la misma clave.
- Migración automática de claves existentes en marca_percents a su forma normalizada.

Tablas (en la base de proveedores):
- lista_percents(lista_id INTEGER PRIMARY KEY, desc REAL NOT NULL DEFAULT 0, iva REAL NOT NULL DEFAULT 0, updated_at TEXT)
- marca_percents(lista_id INTEGER NOT NULL, marca TEXT NOT NULL, desc REAL NOT NULL DEFAULT 0, iva REAL NOT NULL DEFAULT 0, updated_at TEXT,
                 PRIMARY KEY(lista_id, marca))
"""

from datetime import datetime
import unicodedata
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from .bootstrap import bootstrap

_ns = bootstrap()
SessionLocal = _ns["SessionLocal"]

# ------------------------------
# Inicialización de tablas
# ------------------------------
def _ensure_tables():
    ddl_lista = """
    CREATE TABLE IF NOT EXISTS lista_percents (
        lista_id    INTEGER PRIMARY KEY,
        "desc"      REAL NOT NULL DEFAULT 0,
        iva         REAL NOT NULL DEFAULT 0,
        updated_at  TEXT
    );
    """
    ddl_marca = """
    CREATE TABLE IF NOT EXISTS marca_percents (
        lista_id    INTEGER NOT NULL,
        marca       TEXT    NOT NULL,
        "desc"      REAL NOT NULL DEFAULT 0,
        iva         REAL NOT NULL DEFAULT 0,
        updated_at  TEXT,
        PRIMARY KEY (lista_id, marca)
    );
    """
    with SessionLocal() as s:
        try:
            s.execute(text(ddl_lista))
            s.execute(text(ddl_marca))

            # Verificación y migración de columnas (updated_at)
            for table in ["lista_percents", "marca_percents"]:
                try:
                    s.execute(text(f"SELECT updated_at FROM {table} LIMIT 1"))
                except OperationalError:
                    # La columna no existe, la agregamos
                    try:
                        s.execute(text(f"ALTER TABLE {table} ADD COLUMN updated_at TEXT"))
                    except Exception as e:
                        print(f"Error migrando esquema en {table}: {e}")

            s.commit()
        except Exception as e:
            print(f"Error inicializando tablas de costos: {e}")
            s.rollback()

def _strip_accents_upper(s: str) -> str:
    """Quita acentos y pasa a MAYÚSCULAS ASCII."""
    if not s:
        return ""
    # NFKD -> eliminar diacríticos
    nf = unicodedata.normalize("NFKD", s)
    no_acc = "".join(ch for ch in nf if not unicodedata.combining(ch))
    return no_acc.upper()

def _norm_brand(x: str) -> str:
    """
    Normaliza marca: trim, colapsa espacios internos a uno, sin acentos, MAYÚSCULAS.
    """
    s = (x or "").strip()
    # colapsar múltiples espacios (incluyendo tabs) a un solo espacio
    parts = s.split()
    s2 = " ".join(parts)
    return _strip_accents_upper(s2)

def _migrate_brand_keys():
    """
    Normaliza claves existentes en marca_percents.
    Si encuentra una fila (lista_id, marca_no_normalizada) y su versión normalizada,
    fusiona por UPSERT y elimina la no-normalizada.
    """
    sel = text("""SELECT lista_id, marca, "desc", iva, updated_at FROM marca_percents""")
    with SessionLocal() as s:
        try:
            rows = s.execute(sel).all()
        except Exception:
            # Si falla el select (ej. tabla no lista), abortamos migración silenciosamente
            return

        changed = []
        for lid, marca, d, v, ts in rows:
            norm = _norm_brand(marca)
            if norm and norm != marca:
                changed.append((lid, marca, norm, d, v, ts))
        if not changed:
            return
        # aplicar cambios
        ins = text("""
            INSERT INTO marca_percents (lista_id, marca, "desc", iva, updated_at)
            VALUES (:lid, :m, :d, :v, :ts)
            ON CONFLICT(lista_id, marca) DO UPDATE SET
                "desc" = excluded."desc",
                iva    = excluded.iva,
                updated_at = excluded.updated_at
        """)
        dele = text("""DELETE FROM marca_percents WHERE lista_id = :lid AND marca = :m_old""")
        try:
            for lid, m_old, m_new, d, v, ts in changed:
                s.execute(ins, {"lid": int(lid), "m": m_new, "d": float(d or 0.0), "v": float(v or 0.0), "ts": ts or datetime.now().isoformat(timespec="seconds")})
                s.execute(dele, {"lid": int(lid), "m_old": m_old})
            s.commit()
        except Exception as e:
            print(f"Error migrando claves de marca: {e}")
            s.rollback()

try:
    _ensure_tables()
    _migrate_brand_keys()
except Exception as e:
    print(f"Advertencia: No se pudo inicializar el módulo de costos de proveedores: {e}")

# ------------------------------
# Normalizaciones numéricas
# ------------------------------
def _cap_percent(x):
    try:
        v = float(x)
    except Exception:
        v = 0.0
    if v < 0.0: v = 0.0
    if v > 99.99: v = 99.99
    return v

def _norm_str(x):
    return (x or "").strip()

# ------------------------------
# Persistencia: LISTA
# ------------------------------
def save_lista_percents(lista_id: int, desc_pct: float, iva_pct: float):
    """UPSERT de % DESCUENTO e IVA para una lista."""
    d = _cap_percent(desc_pct)
    v = _cap_percent(iva_pct)
    now = datetime.now().isoformat(timespec="seconds")
    sql = text("""
        INSERT INTO lista_percents (lista_id, "desc", iva, updated_at)
        VALUES (:lid, :d, :v, :ts)
        ON CONFLICT(lista_id) DO UPDATE SET
          "desc" = excluded."desc",
          iva    = excluded.iva,
          updated_at = excluded.updated_at
    """)
    with SessionLocal() as s:
        try:
            s.execute(sql, {"lid": int(lista_id), "d": float(d), "v": float(v), "ts": now})
            s.commit()
        except OperationalError:
            s.rollback()
            s.execute(sql, {"lid": int(lista_id), "d": float(d), "v": float(v), "ts": now})
            s.commit()

def get_lista_percents(lista_id: int):
    """Devuelve (desc_pct, iva_pct). Si no hay, (0.0, 0.0)."""
    sql = text("""SELECT "desc", iva FROM lista_percents WHERE lista_id = :lid""")
    with SessionLocal() as s:
        row = s.execute(sql, {"lid": int(lista_id)}).first()
    if not row:
        return 0.0, 0.0
    d, v = row[0], row[1]
    return _cap_percent(d), _cap_percent(v)

# ------------------------------
# Persistencia: MARCA (con normalización)
# ------------------------------
def save_marca_percents(lista_id: int, marca: str, desc_pct: float, iva_pct: float):
    """
    UPSERT de % DESCUENTO e IVA para una MARCA dentro de la lista.
    Usa clave normalizada (sin acentos, mayúsculas, espacios colapsados).
    """
    m = _norm_brand(marca)
    if not m:
        return
    d = _cap_percent(desc_pct)
    v = _cap_percent(iva_pct)
    now = datetime.now().isoformat(timespec="seconds")
    sql = text("""
        INSERT INTO marca_percents (lista_id, marca, "desc", iva, updated_at)
        VALUES (:lid, :m, :d, :v, :ts)
        ON CONFLICT(lista_id, marca) DO UPDATE SET
          "desc" = excluded."desc",
          iva    = excluded.iva,
          updated_at = excluded.updated_at
    """)
    with SessionLocal() as s:
        try:
            s.execute(sql, {"lid": int(lista_id), "m": m, "d": float(d), "v": float(v), "ts": now})
            s.commit()
        except OperationalError:
            s.rollback()
            s.execute(sql, {"lid": int(lista_id), "m": m, "d": float(d), "v": float(v), "ts": now})
            s.commit()

def get_marca_percents(lista_id: int, marca: str):
    """
    Devuelve (desc_pct, iva_pct) o (None, None) si no hay override para la marca.
    La búsqueda es por marca normalizada (coincide aunque varíe acentuación/caso/espacios).
    """
    m = _norm_brand(marca)
    if not m:
        return None, None
    sql = text("""SELECT "desc", iva FROM marca_percents WHERE lista_id = :lid AND marca = :m""")
    with SessionLocal() as s:
        row = s.execute(sql, {"lid": int(lista_id), "m": m}).first()
    if not row:
        return None, None
    d, v = row[0], row[1]
    return _cap_percent(d), _cap_percent(v)

def delete_marca_percents(lista_id: int, marca: str):
    m = _norm_brand(marca)
    if not m:
        return
    sql = text("""DELETE FROM marca_percents WHERE lista_id = :lid AND marca = :m""")
    with SessionLocal() as s:
        try:
            s.execute(sql, {"lid": int(lista_id), "m": m})
            s.commit()
        except OperationalError:
            s.rollback()
            s.execute(sql, {"lid": int(lista_id), "m": m})
            s.commit()

# ------------------------------
# Cálculo centralizado
# ------------------------------
def _to_float_base(x):
    try:
        return float(x)
    except Exception:
        try:
            s = str(x).strip()
            if "," in s and "." in s:
                s = s.replace(".", "").replace(",", ".")
            elif "," in s and "." not in s:
                s = s.replace(",", ".")
            return float(s)
        except Exception:
            return 0.0

def calc_line(base_price, desc_pct, iva_pct):
    """
    Fórmulas:
    - Precio con descuento = Precio de costo - (Precio de costo * desc)
    - Precio con IVA       = Precio con descuento * (1 + iva)
    (desc, iva en %; acotados 0..99.99)
    """
    basef = _to_float_base(base_price)
    d = _cap_percent(desc_pct) / 100.0
    v = _cap_percent(iva_pct) / 100.0

    con_desc = basef - (basef * d)

    # OLD: mas_iva = con_desc / (1 - v)  (incorrecto para IVA)
    # NEW: mas_iva = con_desc * (1 + v)
    mas_iva = con_desc * (1.0 + v)

    return float(basef), float(round(con_desc, 2)), float(round(mas_iva, 2))
