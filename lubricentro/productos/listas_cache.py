# productos/listas_cache.py
from collections import defaultdict
from sqlalchemy import select

def _get_ns():
    from proveedores.bootstrap import bootstrap
    return bootstrap()

def _s(val):
    try:
        return (val or "").strip()
    except Exception:
        try:
            return str(val).strip()
        except Exception:
            return ""

def _num(x):
    s = str(x).strip()
    if s == "":
        return 0.0
    try:
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s and "." not in s:
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        try:
            return float(x)
        except Exception:
            return 0.0

class ListasCache:
    def __init__(self):
        self.by_code = defaultdict(list) # code -> list of dicts
        self.by_desc = defaultdict(list) # desc -> list of dicts
        self.loaded = False

    def load(self):
        if self.loaded:
            return

        _ns = _get_ns()
        ItemListaProveedor = _ns.get("ItemListaProveedor")
        ListaPrecioProveedor = _ns.get("ListaPrecioProveedor")
        ProvSession = _ns.get("SessionLocal")

        if not ProvSession or not ItemListaProveedor or not ListaPrecioProveedor:
            return

        try:
            with ProvSession() as ps:
                # Join with Lista to get provider_id and order by date/id
                stmt = select(
                    ItemListaProveedor.producto_codigo,
                    ItemListaProveedor.descripcion,
                    ItemListaProveedor.marca,
                    ItemListaProveedor.precio,
                    ListaPrecioProveedor.id,
                    ListaPrecioProveedor.proveedor_id,
                    ItemListaProveedor.presentacion,
                    ItemListaProveedor.info_extra
                ).join(
                    ListaPrecioProveedor,
                    ItemListaProveedor.lista_id == ListaPrecioProveedor.id
                ).order_by(ListaPrecioProveedor.id.desc())

                rows = ps.execute(stmt).all()

                for row in rows:
                    # row structure based on select order
                    item = {
                        "codigo": _s(row[0]),
                        "desc": _s(row[1]),
                        "marca": _s(row[2]),
                        "base": _num(row[3]),
                        "lista_id": int(row[4]),
                        "proveedor_id": int(row[5]),
                        "pres": _s(row[6]) if row[6] else "",
                        "extra": _s(row[7]) if row[7] else ""
                    }

                    # Indexing
                    if item["codigo"]:
                        self.by_code[item["codigo"]].append(item)
                    if item["desc"]:
                        self.by_desc[item["desc"]].append(item)

            self.loaded = True
        except Exception as e:
            print(f"Error loading ListasCache: {e}")

    def find_match(self, cod_prov, sku, nombre, proveedor_id=None):
        """
        Replicates find_price_plus_iva_for_product logic.
        Returns the best matching item dict or None.
        """
        if not self.loaded:
            return None

        candidates = []

        force_code_only = bool(cod_prov)

        # Helper to filter by provider if needed
        def _allowed(it):
            if proveedor_id and it["proveedor_id"] != int(proveedor_id):
                return False
            return True

        # Collect candidates with priorities
        # We store (priority, -lista_id, item) so we can sort by priority ASC, then lista_id DESC (via negative)

        # 1. cod_prov -> code (Prio 0)
        if cod_prov:
            for it in self.by_code.get(cod_prov, []):
                if _allowed(it):
                    candidates.append((0, -it["lista_id"], it))

            # cod_prov -> desc (Prio 0 - Description as Code)
            for it in self.by_desc.get(cod_prov, []):
                if _allowed(it):
                    candidates.append((0, -it["lista_id"], it))

        if not force_code_only:
            # 2. sku -> code (Prio 1)
            if sku:
                for it in self.by_code.get(sku, []):
                    if _allowed(it):
                        candidates.append((1, -it["lista_id"], it))

            # 3. nombre -> code (Prio 2 - Description as Code)
            if nombre:
                for it in self.by_code.get(nombre, []):
                    if _allowed(it):
                        candidates.append((2, -it["lista_id"], it))

            # 4. nombre -> desc (Prio 3)
            if nombre:
                for it in self.by_desc.get(nombre, []):
                    if _allowed(it):
                        candidates.append((3, -it["lista_id"], it))

        if not candidates:
            return None

        # Sort: Lowest Priority first, then Newest List (smallest negative list_id)
        candidates.sort(key=lambda x: (x[0], x[1]))

        # Return best item
        return candidates[0][2]
