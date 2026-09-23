from typing import List, Optional, Dict, Any, Tuple
import datetime as dt
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
import openpyxl

# Importamos desde bootstrap de forma segura
try:
    from proveedores.bootstrap import bootstrap
    _ns = bootstrap()
    SessionLocalProv = _ns["SessionLocal"]
    Proveedor = _ns["Proveedor"]
    ListaPrecioProveedor = _ns["ListaPrecioProveedor"]
    ItemListaProveedor = _ns["ItemListaProveedor"]
    MovimientoProveedor = _ns.get("MovimientoProveedor") or _ns.get("MovProveedor")
except Exception:
    SessionLocalProv = None
    Proveedor = None
    ListaPrecioProveedor = None
    ItemListaProveedor = None
    MovimientoProveedor = None

class ProveedorService:
    @staticmethod
    def get_session():
        if SessionLocalProv:
            return SessionLocalProv()
        raise RuntimeError("Proveedor DB no disponible")

    # ---------- Movimientos / Cta Cte ----------
    @classmethod
    def get_movimientos(cls, session: Session) -> List[Any]:
        if not MovimientoProveedor:
            return []
        return (session.query(MovimientoProveedor)
                .order_by(MovimientoProveedor.fecha.asc(), MovimientoProveedor.id.asc())
                .all())

    @classmethod
    def add_movimiento(cls, session: Session, proveedor_id: int,
                       descripcion: str, debe: float = 0.0, haber: float = 0.0,
                       fecha: Optional[dt.date] = None):
        if not MovimientoProveedor:
            return None
        m = MovimientoProveedor(
            proveedor_id=proveedor_id,
            descripcion=descripcion,
            debe=debe,
            haber=haber,
            fecha=fecha or dt.date.today()
        )
        session.add(m)
        session.commit()
        return m

    # ---------- Listas de Precios ----------
    @classmethod
    def get_listas_resumen(cls, session: Session):
        if not ListaPrecioProveedor or not ItemListaProveedor:
            return []

        stmt = (select(ListaPrecioProveedor.id, ListaPrecioProveedor.proveedor_id,
                       ListaPrecioProveedor.nombre, ListaPrecioProveedor.fecha_creacion,
                       func.count(ItemListaProveedor.id).label("n"),
                       func.max(func.coalesce(getattr(ItemListaProveedor,"updated_at",None),
                                              getattr(ListaPrecioProveedor,"fecha_creacion",None))).label("u"))
                .join(ItemListaProveedor, ItemListaProveedor.lista_id==ListaPrecioProveedor.id, isouter=True)
                .group_by(ListaPrecioProveedor.id)
                .order_by(ListaPrecioProveedor.id.desc()))
        return session.execute(stmt).all()

    @classmethod
    def importar_lista_excel(cls, session: Session, proveedor_id: int, file_path: str,
                             mapping: Dict[str, int], sheet_name: str, header_row: int,
                             replace_existing_name: bool = False) -> Tuple[int, int, bool]:
        """
        Importa lista desde Excel.
        Retorna (lista_id, items_insertados, reemplazada_bool)
        """
        if not (ListaPrecioProveedor and ItemListaProveedor):
            raise RuntimeError("Modelos de lista no disponibles")

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb[sheet_name]
        except Exception as e:
            raise RuntimeError(f"Error abriendo Excel: {e}")

        rows = list(ws.iter_rows(values_only=True))
        data_rows = []
        for i, row in enumerate(rows, start=1):
            vals = [("" if v is None else str(v).strip()) for v in row]
            if i > header_row and any(v != "" for v in vals):
                data_rows.append(vals)

        nombre_archivo = file_path.split("/")[-1].replace(".xlsx","").replace(".xls","")
        # En windows paths
        if "\\" in nombre_archivo:
            nombre_archivo = nombre_archivo.split("\\")[-1]

        ahora = dt.date.today()

        # Check existing
        existing_lid = None
        if replace_existing_name:
             row = session.execute(
                select(ListaPrecioProveedor.id).where(
                    ListaPrecioProveedor.proveedor_id==proveedor_id,
                    ListaPrecioProveedor.nombre==nombre_archivo
                ).limit(1)
            ).first()
             if row: existing_lid = int(row[0])

        if existing_lid:
            lst = session.get(ListaPrecioProveedor, existing_lid)
            session.query(ItemListaProveedor).filter_by(lista_id=existing_lid).delete()
            lst.fecha_creacion = ahora
            lid = existing_lid
            reemplazada = True
        else:
            lst = ListaPrecioProveedor(proveedor_id=proveedor_id, nombre=nombre_archivo, fecha_creacion=ahora)
            session.add(lst)
            session.flush()
            lid = lst.id
            reemplazada = False

        insertados = 0

        idx_cod = mapping.get("idx_codigo")
        idx_desc = mapping.get("idx_desc")
        idx_marca = mapping.get("idx_marca")
        idx_prec = mapping.get("idx_precio")
        idx_pres = mapping.get("idx_pres")
        idx_extra = mapping.get("idx_extra")

        for r in data_rows:
            def _get(idx):
                return (r[idx] or "").strip() if idx is not None and idx < len(r) else ""

            codigo = _get(idx_cod)
            desc = _get(idx_desc)
            marca = _get(idx_marca)
            precio_txt = _get(idx_prec)
            pres = _get(idx_pres)
            extra = _get(idx_extra)

            if desc == "" and (codigo == "" or precio_txt == ""): continue

            val_precio = cls._parse_num(precio_txt)

            item = ItemListaProveedor(
                lista_id=lid,
                producto_codigo=codigo,
                descripcion=desc,
                marca=marca,
                precio=val_precio,
                presentacion=pres,
                info_extra=extra
            )
            # Compatibility with legacy models if attributes differ?
            # bootstrap.py defines: producto_codigo, precio, descripcion, marca, rubro_detectado, presentacion, info_extra
            # So standard attributes match.

            session.add(item)
            insertados += 1

        session.commit()
        return lid, insertados, reemplazada

    @staticmethod
    def _parse_num(x):
        s = str(x).strip()
        if s == "": return 0.0
        try:
            if "," in s and "." in s:
                s = s.replace(".", "").replace(",", ".")
            elif "," in s and "." not in s:
                s = s.replace(",", ".")
            return float(s)
        except Exception:
            try: return float(x)
            except Exception: return 0.0
