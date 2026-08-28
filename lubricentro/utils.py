# utils.py
# ===========================
# Funciones auxiliares y utilidades compartidas
# ===========================

import os
import sqlite3
import datetime as dt
from typing import List, Dict, Optional, Tuple

import pandas as pd

# pdf -> tabla (opcional)
try:
    import camelot  # type: ignore
    _HAS_CAMELOT = True
except Exception:
    _HAS_CAMELOT = False

import pdfplumber

from PyQt5.QtWidgets import QScrollArea, QMessageBox
from PyQt5.QtCore import Qt
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

from db import (
    SessionLocal, Venta, VentaItem, Configuracion,
    Producto, Stock, Deposito, Marca,
    Proveedor, ProveedorPrecio
)

# --------------------------
# Rutas y directorios
# --------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(APP_DIR, "reportes")
os.makedirs(REPORTS_DIR, exist_ok=True)


# --------------------------
# Helpers ORM
# --------------------------
def get_or_create(session, model, defaults=None, **kwargs):
    """Devuelve una instancia si existe, sino la crea."""
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    params = dict(**kwargs)
    if defaults:
        params.update(defaults)
    instance = model(**params)
    session.add(instance)
    session.commit()
    return instance


def ensure_column(db_path: str, table: str, column: str, ddl_fragment: str):
    """Asegura que una columna exista en una tabla SQLite."""
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(f"PRAGMA table_info({table});")
        cols = [r[1] for r in cur.fetchall()]
        if column not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_fragment};")
            con.commit()
    finally:
        con.close()


# --------------------------
# Normalización y selección
# --------------------------
def normalizar_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia nombres de columnas a minúscula sin espacios extras."""
    cols = {c: c.strip().lower() if isinstance(c, str) else c for c in df.columns}
    return df.rename(columns=cols)


def pick(row, df_cols: List[str], keys: List[str]):
    """Devuelve el valor de la primera columna encontrada en keys."""
    for k in keys:
        if k in df_cols:
            return row.get(k)
    return None


# --------------------------
# UI helpers
# --------------------------
def with_scroll(widget):
    """Envuelve un QWidget en un scroll vertical."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(widget)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    return scroll


# --------------------------
# Formateo / parsing de moneda
# --------------------------
def limpiar_moneda_a_float(val) -> float:
    """Convierte entradas tipo '$ 1.234,56' / '1,234.56' / '1234,56' a float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return 0.0
    s = s.replace('$', '').replace('ARS', '').replace('usd', '').replace('USD', '')
    s = s.replace(' ', '')
    # si hay coma y punto, decidir separador decimal por último símbolo
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    else:
        # sólo coma => decimal
        if ',' in s:
            s = s.replace('.', '').replace(',', '.')
        else:
            # sólo punto => decimal
            pass
    try:
        return float(s)
    except Exception:
        try:
            return float(''.join(ch for ch in s if (ch.isdigit() or ch == '.')))
        except Exception:
            return 0.0


def fmt_money(v: Optional[float]) -> str:
    try:
        return f"${float(v or 0):.2f}"
    except Exception:
        return "$0.00"


# --------------------------
# Remitos (número + PDF)
# --------------------------
def next_remito_number(session):
    """Devuelve el próximo número de remito."""
    last = session.query(Venta).order_by(Venta.numero.desc()).first()
    return (last.numero + 1) if (last and last.numero) else 1


def generar_remito_pdf(conf: Configuracion, venta: Venta, session) -> str:
    """Genera un PDF de remito y devuelve la ruta."""
    filename = f"Remito_{venta.numero:06d}.pdf"
    path = os.path.join(REPORTS_DIR, filename)
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    y = h - 20 * mm

    # Logo
    if conf.logo_path and os.path.exists(conf.logo_path):
        try:
            c.drawImage(conf.logo_path, 15 * mm, y - 15 * mm, width=25 * mm, height=15 * mm,
                        preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # Datos negocio
    c.setFont("Helvetica-Bold", 14)
    c.drawString(45 * mm, y, conf.nombre_negocio or "")
    c.setFont("Helvetica", 10)
    c.drawString(45 * mm, y - 6 * mm, f"CUIT: {conf.cuit or '--'}")
    c.drawString(45 * mm, y - 12 * mm, conf.direccion or "")

    # Datos remito
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(w - 15 * mm, y, f"Remito N° {venta.numero:06d}")
    c.setFont("Helvetica", 10)
    c.drawRightString(w - 15 * mm, y - 6 * mm, f"Fecha: {venta.fecha.strftime('%d/%m/%Y %H:%M')}")
    c.drawRightString(w - 15 * mm, y - 12 * mm, f"Pago: {venta.forma_pago}")

    # Encabezado tabla
    y -= 25 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(15 * mm, y, "Código")
    c.drawString(45 * mm, y, "Descripción")
    c.drawRightString(140 * mm, y, "Cant.")
    c.drawRightString(170 * mm, y, "P.Unit")
    c.drawRightString(195 * mm, y, "Subtotal")
    y -= 4 * mm
    c.line(15 * mm, y, 195 * mm, y)
    y -= 4 * mm

    # Items
    c.setFont("Helvetica", 10)
    for it in session.query(VentaItem).filter_by(venta_id=venta.id).all():
        if y < 30 * mm:
            c.showPage(); y = h - 20 * mm
        cb = it.producto.codigo_barras or "-"
        c.drawString(15 * mm, y, cb[:20])
        c.drawString(45 * mm, y, (it.producto.nombre or "")[:42])
        c.drawRightString(140 * mm, y, f"{it.cantidad:.2f}")
        c.drawRightString(170 * mm, y, f"{it.precio_unitario:.2f}")
        c.drawRightString(195 * mm, y, f"{it.subtotal:.2f}")
        y -= 6 * mm

    # Totales
    y -= 4 * mm
    c.line(120 * mm, y, 195 * mm, y)
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(170 * mm, y, "Total Neto:")
    c.drawRightString(195 * mm, y, f"{venta.total_neto:.2f}")
    y -= 6 * mm
    c.drawRightString(170 * mm, y, "IVA:")
    c.drawRightString(195 * mm, y, f"{venta.total_iva:.2f}")
    y -= 6 * mm
    c.drawRightString(170 * mm, y, "Total:")
    c.drawRightString(195 * mm, y, f"{venta.total:.2f}")

    c.showPage()
    c.save()
    return path


# --------------------------
# Importadores de productos y stock
# --------------------------
def importar_excel_productos_stock(path: str, rubro: str, deposito_nombre: str = 'Principal'):
    """Importa productos/stock desde Excel (para carga inicial)."""
    session = SessionLocal()
    try:
        xls = pd.ExcelFile(path)
        hojas = {h.lower(): h for h in xls.sheet_names}
        dfs = []
        for key, real in hojas.items():
            if any(k in key for k in ['precio', 'stock', 'publico', 'invent']):
                try:
                    dfi = xls.parse(real)
                    dfi['__hoja__'] = real
                    dfs.append(dfi)
                except Exception:
                    pass
        if not dfs:
            raise ValueError('No se encontraron hojas de precios/stock.')
        data = pd.concat(dfs, ignore_index=True)
        data = normalizar_cols(data)
        df_cols = list(data.columns)
        deposito = get_or_create(session, Deposito, nombre=deposito_nombre)

        for _, row in data.iterrows():
            cb = str(pick(row, df_cols, ['codigo_barras', 'código de barras', 'cb', 'ean']) or '').strip()
            nombre = str(pick(row, df_cols, ['nombre', 'producto', 'descripcion']) or '').strip()
            if not (cb or nombre):
                continue
            precio = limpiar_moneda_a_float(pick(row, df_cols, ['precio', 'precio publico', 'precio público']) or 0)
            costo = limpiar_moneda_a_float(pick(row, df_cols, ['costo', 'coste']) or 0)
            stock_val = limpiar_moneda_a_float(pick(row, df_cols, ['stock', 'cantidad', 'existencia']) or 0)
            marca_nom = pick(row, df_cols, ['marca']) or None

            marca = get_or_create(session, Marca, nombre=str(marca_nom).strip()) if marca_nom else None

            prod = None
            if cb:
                prod = session.query(Producto).filter(Producto.codigo_barras == cb).first()
            if not prod and nombre:
                prod = session.query(Producto).filter(Producto.nombre == nombre).first()

            if not prod:
                prod = Producto(
                    codigo_barras=cb if cb else None,
                    nombre=nombre,
                    rubro=rubro,
                    marca=marca,
                    precio_minorista=float(precio or 0),
                    costo=float(costo or 0),
                )
                session.add(prod)
                session.commit()
            else:
                prod.rubro = prod.rubro or rubro
                if precio not in (None, ''): prod.precio_minorista = float(precio or 0)
                if costo  not in (None, ''): prod.costo = float(costo or 0)
                if marca and not prod.marca: prod.marca = marca
                session.commit()

            st = session.query(Stock).filter_by(producto_id=prod.id, deposito_id=deposito.id).first()
            if not st:
                st = Stock(producto_id=prod.id, deposito_id=deposito.id, stock_actual=float(stock_val or 0))
                session.add(st)
            else:
                try:
                    st.stock_actual = float(st.stock_actual or 0) + float(stock_val or 0)
                except Exception:
                    pass
            session.commit()

        QMessageBox.information(None, 'Importación OK', f'Productos importados en rubro {rubro}.')
    except Exception as e:
        QMessageBox.critical(None, 'Error importación', str(e))
    finally:
        session.close()


# --------------------------
# Importadores de proveedores
# --------------------------
def importar_excel_proveedores(path: str, proveedor_nombre: Optional[str] = None):
    """Importa lista de precios de proveedor desde Excel (automático)."""
    session = SessionLocal()
    try:
        xls = pd.ExcelFile(path)
        proveedor = get_or_create(session, Proveedor,
                                  nombre=proveedor_nombre or os.path.splitext(os.path.basename(path))[0])
        for hoja in xls.sheet_names:
            df = xls.parse(hoja)
            df = normalizar_cols(df)
            cols = list(df.columns)
            for _, row in df.iterrows():
                codigo = str(pick(row, cols, ['codigo', 'sku', 'cb']) or '').strip()
                nombre = str(pick(row, cols, ['nombre', 'producto', 'descripcion']) or '').strip()
                precio = limpiar_moneda_a_float(pick(row, cols, ['precio', 'precio publico', 'lista']) or 0)
                if not (nombre or codigo):
                    continue
                pp = ProveedorPrecio(
                    proveedor_id=proveedor.id,
                    codigo=codigo or None,
                    nombre=nombre,
                    precio=float(precio or 0),
                    fecha=dt.datetime.utcnow()
                )
                session.add(pp)
        session.commit()

        actualizar_costos_con_mejor_precio()
        QMessageBox.information(None, 'Importación OK',
                                f'Lista de "{proveedor.nombre}" importada y costos actualizados.')
    except Exception as e:
        QMessageBox.critical(None, 'Error importación', str(e))
    finally:
        session.close()


def importar_excel_proveedores_mapeado(path: str, proveedor_id: int, mapping: Dict[str, str]):
    """
    Importa lista desde Excel con mapeo manual de columnas.
    mapping = {'codigo': 'colX', 'nombre': 'colY', 'precio': 'colZ'}  # 'marca' opcional (no se persiste)
    """
    session = SessionLocal()
    try:
        xls = pd.ExcelFile(path)
        for hoja in xls.sheet_names:
            df = xls.parse(hoja)
            df = normalizar_cols(df)
            cols = list(df.columns)

            col_codigo = mapping.get('codigo')
            col_nombre = mapping.get('nombre')
            col_precio = mapping.get('precio')
            # 'marca' aceptada pero no guardada (no está en el modelo actual)
            # col_marca = mapping.get('marca')

            if not col_nombre or not col_precio:
                raise ValueError("Debe mapear al menos 'nombre' y 'precio'.")

            for _, row in df.iterrows():
                codigo = str(row.get(col_codigo)).strip() if col_codigo and row.get(col_codigo) is not None else None
                nombre = str(row.get(col_nombre)).strip() if row.get(col_nombre) is not None else None
                if not (nombre or codigo):
                    continue
                precio = limpiar_moneda_a_float(row.get(col_precio))
                pp = ProveedorPrecio(
                    proveedor_id=proveedor_id,
                    codigo=codigo or None,
                    nombre=nombre,
                    precio=float(precio or 0),
                    fecha=dt.datetime.utcnow()
                )
                session.add(pp)

        session.commit()
        actualizar_costos_con_mejor_precio()
        QMessageBox.information(None, 'Importación OK', 'Lista importada con mapeo manual y costos actualizados.')
    except Exception as e:
        QMessageBox.critical(None, 'Error importación (mapeado)', str(e))
    finally:
        session.close()


def importar_pdf_proveedores(path: str, proveedor_nombre: Optional[str] = None):
    """
    Importa lista de proveedor desde PDF:
      1) Intenta con Camelot (si está disponible).
      2) Fallback a pdfplumber (tablas simples).
    """
    session = SessionLocal()
    try:
        proveedor = get_or_create(session, Proveedor,
                                  nombre=proveedor_nombre or os.path.splitext(os.path.basename(path))[0])

        registros: List[Tuple[Optional[str], str, float]] = []  # (codigo, nombre, precio)

        if _HAS_CAMELOT:
            try:
                # Probar ambos sabores
                for flavor in ("lattice", "stream"):
                    tables = camelot.read_pdf(path, flavor=flavor, pages="all")
                    for t in tables:
                        df = t.df
                        df = normalizar_cols(df)
                        # Heurística: buscar columnas probables
                        cols = list(df.columns)
                        for _, row in df.iterrows():
                            # Intentar primeras 3 columnas como (codigo, nombre, precio)
                            c0 = str(row.iloc[0]).strip() if len(row) > 0 else None
                            c1 = str(row.iloc[1]).strip() if len(row) > 1 else None
                            c2 = row.iloc[2] if len(row) > 2 else None

                            # ajustar si hay títulos de columnas
                            if c0 and c0.lower() in ("codigo", "código", "sku") and c1 and c1.lower() in ("nombre", "producto", "descripcion"):
                                continue

                            nombre = c1 or c0
                            if not nombre:
                                continue
                            codigo = c0 if c0 and c0 != nombre else None
                            precio = limpiar_moneda_a_float(c2)
                            if precio <= 0 and len(row) > 3:
                                precio = limpiar_moneda_a_float(row.iloc[-1])
                            registros.append((codigo, nombre, float(precio or 0)))
            except Exception:
                # si Camelot falla seguimos con pdfplumber
                pass

        # Fallback pdfplumber (o complemento)
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables() or []
                for tbl in tables:
                    for row in tbl:
                        if not row or len(row) < 2:
                            continue
                        codigo = str(row[0]).strip() if row[0] else None
                        nombre = str(row[1]).strip() if row[1] else None
                        precio_val = 0
                        if len(row) > 2 and row[2]:
                            precio_val = limpiar_moneda_a_float(row[2])
                        elif len(row) > 3 and row[-1]:
                            precio_val = limpiar_moneda_a_float(row[-1])
                        if not (nombre or codigo):
                            continue
                        registros.append((codigo, nombre or (codigo or ""), float(precio_val or 0)))

        # Persistir
        for codigo, nombre, precio in registros:
            pp = ProveedorPrecio(
                proveedor_id=proveedor.id,
                codigo=codigo,
                nombre=nombre,
                precio=float(precio or 0),
                fecha=dt.datetime.utcnow()
            )
            session.add(pp)
        session.commit()

        actualizar_costos_con_mejor_precio()
        QMessageBox.information(None, 'Importación OK',
                                f'PDF de proveedor "{proveedor.nombre}" importado y costos actualizados.')
    except Exception as e:
        QMessageBox.critical(None, 'Error importación PDF', str(e))
    finally:
        session.close()


# --------------------------
# Operaciones sobre listas de proveedor
# --------------------------
def borrar_precios_proveedor_por_ids(proveedor_id: int, ids: List[int]) -> int:
    """Borra selectivamente registros de ProveedorPrecio por ID y devuelve cantidad eliminada."""
    if not ids:
        return 0
    session = SessionLocal()
    try:
        q = session.query(ProveedorPrecio).filter(
            ProveedorPrecio.proveedor_id == proveedor_id,
            ProveedorPrecio.id.in_(ids)
        )
        count = q.count()
        q.delete(synchronize_session=False)
        session.commit()
        return count
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def comparar_df_precios(df_old: pd.DataFrame, df_new: pd.DataFrame,
                        key_cols: Tuple[str, str] = ("codigo", "nombre")) -> Dict[str, int]:
    """
    Compara dos dataframes de precios (campos: codigo, nombre, precio).
    Devuelve métricas para verificación rápida.
    """
    def keyify(df):
        k1, k2 = key_cols
        df = df.copy()
        df[k1] = df.get(k1, "").fillna("").astype(str).str.strip()
        df[k2] = df.get(k2, "").fillna("").astype(str).str.strip()
        df["__key__"] = df[k1].where(df[k1] != "", df[k2])  # usa codigo, si no hay usa nombre
        return df

    o = keyify(df_old)
    n = keyify(df_new)

    left = o[["__key__", "precio"]].rename(columns={"precio": "precio_old"})
    right = n[["__key__", "precio"]].rename(columns={"precio": "precio_new"})
    merged = pd.merge(left, right, on="__key__", how="outer")

    inc = (merged["precio_new"].fillna(0) > merged["precio_old"].fillna(0)).sum()
    dec = (merged["precio_new"].fillna(0) < merged["precio_old"].fillna(0)).sum()
    eq = (merged["precio_new"].fillna(0) == merged["precio_old"].fillna(0)).sum()
    only_old = merged["precio_new"].isna().sum()
    only_new = merged["precio_old"].isna().sum()

    return {
        "aumentos": int(inc),
        "bajas": int(dec),
        "iguales": int(eq),
        "salen": int(only_old),
        "entran": int(only_new),
        "total_new": int(len(n)),
        "total_old": int(len(o)),
    }


# --------------------------
# Actualización automática de costos
# --------------------------
def actualizar_costos_con_mejor_precio():
    """
    Recorre todos los productos y busca en ProveedorPrecio
    el precio más bajo disponible (por código o por nombre).
    Actualiza el costo del producto con ese valor.
    """
    session = SessionLocal()
    try:
        productos = session.query(Producto).all()
        actualizados = 0

        for prod in productos:
            # Buscar por código si existe, sino por nombre
            if prod.codigo_barras:
                registros = session.query(ProveedorPrecio).filter(
                    ProveedorPrecio.codigo == prod.codigo_barras
                ).all()
            else:
                registros = session.query(ProveedorPrecio).filter(
                    ProveedorPrecio.nombre == prod.nombre
                ).all()

            if not registros:
                continue

            menor = min(registros, key=lambda pp: pp.precio if pp.precio else float("inf"))

            if menor and menor.precio and menor.precio > 0:
                if float(prod.costo or 0) != float(menor.precio):
                    prod.costo = float(menor.precio)
                    actualizados += 1

        session.commit()
        if actualizados:
            try:
                QMessageBox.information(None, "Actualización de costos",
                                        f"Se actualizaron {actualizados} productos con el mejor precio disponible.")
            except Exception:
                # En caso de que no haya UI disponible (scripts headless)
                pass
    except Exception as e:
        try:
            QMessageBox.critical(None, "Error al actualizar costos", str(e))
        except Exception:
            pass
    finally:
        session.close()


# --------------------------
# Seguridad simple
# --------------------------
def validar_password(pwd: str) -> bool:
    """
    Valida contra Configuracion.clave_admin (default '1234' si no configurado).
    """
    try:
        with SessionLocal() as s:
            conf = s.query(Configuracion).first()
            clave = (conf.clave_admin if conf and conf.clave_admin else "1234")
            return str(pwd) == str(clave)
    except Exception:
        return str(pwd) == "1234"
