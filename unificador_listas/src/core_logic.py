from unificador_listas.src.database import get_readonly_connection
import sqlite3

def load_maestro_indices():
    """Carga índices desde barterplus.db para Falla 6 (Colisión de Códigos Cortos)."""
    conn = get_readonly_connection()
    if not conn:
        return {}, {}, {}

    por_sku = {}
    por_cod_prov = {}
    por_descripcion_normalizada = {}

    try:
        c = conn.cursor()
        # Intentar determinar columnas (fallback a id, cod_prov, desc, marca si fallan)
        c.execute("PRAGMA table_info(productos)")
        cols = [row[1] for row in c.fetchall()]

        if not cols:
            return {}, {}, {}

        cod_col = "codigo_proveedor" if "codigo_proveedor" in cols else "cod_prov"
        desc_col = "descripcion" if "descripcion" in cols else "nombre"
        marca_col = "marca" if "marca" in cols else "rubro"

        c.execute(f"SELECT sku, {cod_col}, {desc_col}, {marca_col} FROM productos")
        for row in c.fetchall():
            sku, cod_prov, desc, marca = row
            if sku: por_sku[str(sku).upper()] = row
            if cod_prov:
                key_cod = str(cod_prov).upper().strip()
                if key_cod not in por_cod_prov:
                    por_cod_prov[key_cod] = []
                por_cod_prov[key_cod].append(row)
            if desc:
                key_desc = str(desc).upper().strip()
                por_descripcion_normalizada[key_desc] = row

    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return por_sku, por_cod_prov, por_descripcion_normalizada

def validar_colision(cod_prov_extraido, desc_extraida, proveedor_ingresado, indices_db):
    """
    Doble candado anti-colisión para códigos cortos (Falla 6).
    indices_db = (por_sku, por_cod_prov, por_descripcion_normalizada)
    Devuelve "ACTUALIZACION" si es el mismo repuesto, "NUEVO" si es colisión de rubro.
    """
    por_sku, por_cod_prov, por_desc = indices_db

    cod_clean = str(cod_prov_extraido).upper().strip()

    if cod_clean not in por_cod_prov:
        return "NUEVO"

    # Es un código corto o puramente numérico (ej: "105", "10")
    if len(cod_clean) < 5 or cod_clean.isdigit():
        coincidencias = por_cod_prov[cod_clean]

        for match in coincidencias:
            sku_db, cod_db, desc_db, marca_db = match

            # 1. Coincidencia de proveedor (en base al SKU que suele ser PROV-COD)
            prefijo_prov = str(proveedor_ingresado)[:3].upper()
            if sku_db and sku_db.startswith(prefijo_prov):
                return "ACTUALIZACION"

            # 2. Similitud semántica (al menos comparte una palabra clave larga de la descripción o la marca)
            desc_db_upper = str(desc_db).upper()
            desc_ext_upper = str(desc_extraida).upper()

            # Buscar marca en la descripción extraída
            if marca_db and str(marca_db).upper() in desc_ext_upper:
                return "ACTUALIZACION"

            # Buscar palabras clave (más de 4 letras)
            palabras_db = set([p for p in desc_db_upper.split() if len(p) > 4])
            palabras_ext = set([p for p in desc_ext_upper.split() if len(p) > 4])

            if palabras_db.intersection(palabras_ext):
                return "ACTUALIZACION"

        # Si no pasó ninguno de los candados, es una colisión de código corto entre rubros distintos
        return "NUEVO"

    return "ACTUALIZACION"
