import streamlit as st
import sqlite3
import pandas as pd
import pdfplumber
import re
from datetime import datetime
from thefuzz import fuzz
import io

DB_NAME = "master_data.db"
NONE_OPTION = "[Ninguno (No Existe)]"

@st.cache_resource
def run_init_db():
    init_db()

def init_db():
    """
    Base de Datos Resiliente (init_db)
    Inicializa el esquema y corrige dinámicamente cualquier columna faltante.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Tabla Principal
    c.execute('''
        CREATE TABLE IF NOT EXISTS productos_maestro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_interno TEXT UNIQUE,
            codigo_proveedor TEXT,
            descripcion TEXT,
            marca TEXT,
            tipo_venta TEXT,
            capacidad_medida TEXT,
            contenido_caja TEXT,
            costo_actual REAL,
            fecha_actualizacion TEXT
        )
    ''')

    # Tabla de Plantillas de Mapeo
    c.execute('''
        CREATE TABLE IF NOT EXISTS plantillas_proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proveedor_marca TEXT UNIQUE,
            col_codigo TEXT,
            col_descripcion TEXT,
            col_costo TEXT,
            col_contenido_caja TEXT
        )
    ''')

    # Módulo de Auto-Corrección: Inspección física de productos_maestro
    c.execute("PRAGMA table_info(productos_maestro)")
    columns = [info[1] for info in c.fetchall()]

    required_columns = {
        'sku_interno': 'TEXT UNIQUE',
        'tipo_venta': 'TEXT',
        'capacidad_medida': 'TEXT',
        'contenido_caja': 'TEXT',
        'costo_actual': 'REAL'
    }

    for col, dtype in required_columns.items():
        if col not in columns:
            try:
                c.execute(f"ALTER TABLE productos_maestro ADD COLUMN {col} {dtype}")
                st.toast(f"🛠️ Autocorrección de BD: Columna '{col}' agregada a productos_maestro.", icon="🔧")
            except sqlite3.OperationalError as e:
                if 'UNIQUE' in dtype:
                   c.execute(f"ALTER TABLE productos_maestro ADD COLUMN {col} TEXT")
                else:
                    raise e

    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_NAME)

def purge_dataframe_advanced(df):
    """
    Módulo de Purga Resiliente
    Descarta filas vacías, disclaimers y cabeceras operativas, devolviendo también
    la cantidad de filas omitidas para el reporte visual.
    """
    if df is None or df.empty:
        return df, 0

    original_count = len(df)

    # 1. Blindar el DataFrame
    df.columns = [f"Col_{i}" for i in range(len(df.columns))]

    # 2. Limpieza de Vacíos
    df = df.replace(r'^\s*$', pd.NA, regex=True)
    df = df.dropna(how='all')

    if df.empty:
        return df, original_count

    # Regex para basura y disclaimers
    disclaimer_pattern = re.compile(r'(LISTA SUJETA A CAMBIOS|NO INCLUYE IVA|VÁLIDA HASTA|VALIDA HASTA|CONFIRMAR PRECIOS|PAGINA \d+|SOLO CONTADO|LOS PRECIOS|RAMONSABIO)', re.IGNORECASE)
    header_pattern = re.compile(r'\b(CÓDIGO|CODIGO|DESCRIPCIÓN|DESCRIPCION|NETO|PRECIO|PRODUCTO|FILTROS|ACEITES|MARCA)\b', re.IGNORECASE)

    rows_to_keep = []

    for index, row in df.iterrows():
        row_str = " ".join([str(val) for val in row if pd.notna(val)])

        # Filtro de disclaimers
        if disclaimer_pattern.search(row_str):
            continue

        # Filtro de cabeceras operativas (Si más del 50% de celdas válidas son cabeceras)
        header_matches = 0
        valid_cells = 0
        for val in row:
            if pd.notna(val) and str(val).strip():
                valid_cells += 1
                if header_pattern.search(str(val)):
                    header_matches += 1

        if valid_cells > 0 and (header_matches / valid_cells) > 0.5:
            continue

        rows_to_keep.append(index)

    purged_df = df.loc[rows_to_keep].reset_index(drop=True)
    omitted_count = original_count - len(purged_df)

    return purged_df, omitted_count

def detect_unit_and_capacity(description):
    """
    Clasifica automáticamente el Tipo_Venta (UNIDAD o GRANEL) y la Capacidad.
    """
    desc_upper = str(description).upper()
    tipo_venta = "UNIDAD"
    capacidad_medida = "Unidad"

    match_granel = re.search(r'\b(TAMBOR|TBR|200\s*L|GRANEL|BALDE|20\s*L)\b', desc_upper)
    if match_granel:
        tipo_venta = "GRANEL"
        cap = match_granel.group(1).replace(" ", "")
        if "200L" in cap:
            capacidad_medida = "200L"
        elif "20L" in cap:
            capacidad_medida = "20L"
        elif cap in ["TAMBOR", "TBR"]:
            capacidad_medida = "Tambor"
        elif cap == "BALDE":
            capacidad_medida = "Balde"
        else:
            capacidad_medida = "Granel"
    else:
        match_unidad = re.search(r'\b(\d+\s*L|BOTELLA|UNIDAD|FILTRO)\b', desc_upper)
        if match_unidad:
            cap = match_unidad.group(1).replace(" ", "")
            if "L" in cap and cap[0].isdigit():
                capacidad_medida = cap
            elif cap == "BOTELLA":
                capacidad_medida = "Botella"
            elif cap == "FILTRO":
                capacidad_medida = "Filtro"
            else:
                capacidad_medida = "Unidad"

    return tipo_venta, capacidad_medida

def generate_sku(marca, tipo_venta, item_id):
    """
    Generador de SKU Propio Unificado: [MARCA]-[UN/GR]-[ID_AUTONUMERICO]
    """
    marca_prefix = str(marca)[:3].upper() if len(str(marca)) >= 3 else str(marca).upper().ljust(3, 'X')
    tipo_code = "UN" if tipo_venta == "UNIDAD" else "GR"
    return f"{marca_prefix}-{tipo_code}-{str(item_id).zfill(5)}"

def clean_currency(value):
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    value_str = str(value).replace('$', '').replace(',', '').strip()
    try:
        return float(value_str)
    except ValueError:
        return 0.0

def clean_box_content(value):
    if pd.isna(value) or str(value).strip() == "":
         return "1"
    val_str = str(value).strip()
    match = re.search(r'(\d+)', val_str)
    if match:
         return match.group(1)
    return "1"

def process_mass_update(df, marca, template):
    """
    Procesa un dataframe aplicando estrictamente la plantilla.
    Cruza por Marca y Tipo de Venta usando exact match -> fuzzy match.
    Retorna (insertados, actualizados, ignorados_vacios, reporte_lista).
    """
    col_codigo = template['col_codigo']
    col_desc = template['col_descripcion']
    col_costo = template['col_costo']
    col_caja = template['col_contenido_caja']

    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT id, codigo_proveedor, descripcion, tipo_venta FROM productos_maestro WHERE marca = ?", (marca,))
    db_items = c.fetchall()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updates = 0
    inserts = 0
    ignorados = 0

    report_list = []

    for _, row in df.iterrows():
        cod_prov = str(row[col_codigo]).strip() if col_codigo != NONE_OPTION and col_codigo in df.columns and pd.notna(row[col_codigo]) else ""
        desc = str(row[col_desc]).strip() if col_desc != NONE_OPTION and col_desc in df.columns and pd.notna(row[col_desc]) else ""
        costo = clean_currency(row[col_costo]) if col_costo != NONE_OPTION and col_costo in df.columns else 0.0
        caja = clean_box_content(row[col_caja]) if col_caja != NONE_OPTION and col_caja in df.columns else "1"

        if not desc or desc.lower() in ['nan', 'none', '']:
            ignorados += 1
            continue

        tipo_venta, capacidad = detect_unit_and_capacity(desc)
        matched_id = None

        # 1. Match Exacto por Código Proveedor y Tipo de Venta
        if cod_prov and cod_prov.lower() not in ['nan', 'none']:
            for item in db_items:
                if item[1] == cod_prov and item[3] == tipo_venta:
                    matched_id = item[0]
                    break

        # 2. Match Fuzzy Inteligente
        if not matched_id:
            best_score = 0
            best_id = None
            for item in db_items:
                if item[3] == tipo_venta:
                    score = fuzz.token_sort_ratio(desc.lower(), item[2].lower())
                    if score > best_score:
                        best_score = score
                        best_id = item[0]

            if best_score >= 85:
                matched_id = best_id

        if matched_id:
            c.execute('''UPDATE productos_maestro
                         SET costo_actual = ?, fecha_actualizacion = ?, contenido_caja = ?, capacidad_medida = ?
                         WHERE id = ?''', (costo, now, caja, capacidad, matched_id))

            c.execute("SELECT sku_interno FROM productos_maestro WHERE id = ?", (matched_id,))
            sku_val = c.fetchone()[0]

            report_list.append({'Acción': 'Actualizado', 'SKU': sku_val, 'Descripción': desc, 'Costo': costo})
            updates += 1
        else:
            c.execute('''INSERT INTO productos_maestro
                         (codigo_proveedor, descripcion, marca, tipo_venta, capacidad_medida, contenido_caja, costo_actual, fecha_actualizacion)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                         (cod_prov, desc, marca, tipo_venta, capacidad, caja, costo, now))
            new_id = c.lastrowid
            sku = generate_sku(marca, tipo_venta, new_id)
            c.execute("UPDATE productos_maestro SET sku_interno = ? WHERE id = ?", (sku, new_id))

            db_items.append((new_id, cod_prov, desc, tipo_venta))
            report_list.append({'Acción': 'NUEVO', 'SKU': sku, 'Descripción': desc, 'Costo': costo})
            inserts += 1

    conn.commit()
    conn.close()

    return inserts, updates, ignorados, report_list

def parse_raw_file(uploaded_file):
    filename = uploaded_file.name.lower()
    try:
        if filename.endswith(('.xls', '.xlsx')):
            xl = pd.ExcelFile(uploaded_file)
            df = pd.read_excel(xl, sheet_name=xl.sheet_names[0], header=None)
            df.columns = [f"Col_{i}" for i in range(len(df.columns))]
            return df
        elif filename.endswith('.pdf'):
            data = []
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        data.extend(table)
            if data:
                df = pd.DataFrame(data)
                df.columns = [f"Col_{i}" for i in range(len(df.columns))]
                return df
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
        return pd.DataFrame()

def process_file_advanced(uploaded_file):
    """
    Retorna una lista de DataFrames purgados (uno por pestaña de Excel o la única tabla del PDF)
    junto con la cantidad total de filas omitidas.
    """
    filename = uploaded_file.name.lower()
    blocks = []
    total_omitted = 0
    try:
        if filename.endswith(('.xls', '.xlsx')):
            xl = pd.ExcelFile(uploaded_file)
            for sheet in xl.sheet_names:
                df = pd.read_excel(xl, sheet_name=sheet, header=None)
                df_purged, omitted = purge_dataframe_advanced(df)
                total_omitted += omitted
                if not df_purged.empty:
                    blocks.append(df_purged)
        elif filename.endswith('.pdf'):
            data = []
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        data.extend(table)
            if data:
                df = pd.DataFrame(data)
                df_purged, omitted = purge_dataframe_advanced(df)
                total_omitted += omitted
                if not df_purged.empty:
                    blocks.append(df_purged)
    except Exception as e:
        st.error(f"Error en extracción: {e}")
    return blocks, total_omitted

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario Maestro')
    return output.getvalue()


def main():
    st.set_page_config(page_title="Gestor de Ingesta Guiado (Barter Plus)", layout="wide")

    run_init_db()

    # ---------------- SIDEBAR: MÓDULO DE MAPEO GUIADO ----------------
    with st.sidebar:
        st.header("Gestión de Plantillas")
        st.info("Sube un ejemplo para enseñar al sistema dónde están los datos de este proveedor.")

        train_file = st.file_uploader("Subir Archivo de Ejemplo", type=["xlsx", "xls", "pdf"], key="train_file")
        train_marca = st.text_input("Nombre del Proveedor / Marca", key="train_marca").strip().upper()

        if train_file and train_marca:
            if st.button("Previsualizar Estructura", key="btn_train"):
                df_train = parse_raw_file(train_file)
                if not df_train.empty:
                    st.session_state['df_train_raw'] = df_train
                else:
                    st.error("No se pudo extraer la estructura cruda.")

        if 'df_train_raw' in st.session_state:
            df_train_raw = st.session_state['df_train_raw']
            st.dataframe(df_train_raw.head(10))

            cols = [NONE_OPTION] + list(df_train_raw.columns)

            st.write("**Define los Índices:**")
            map_cod = st.selectbox("¿Dónde está el CÓDIGO?", cols, key="map_cod")
            map_desc = st.selectbox("¿Dónde está la DESCRIPCIÓN?", [c for c in cols if c != NONE_OPTION], key="map_desc")
            map_neto = st.selectbox("¿Dónde está el NETO (Precio)?", cols, key="map_neto")
            map_caja = st.selectbox("¿Dónde está Unidades x Caja? (Opcional)", cols, key="map_caja")

            if st.button("Guardar Plantilla", key="btn_save_tpl"):
                conn = get_connection()
                c = conn.cursor()
                try:
                    c.execute('''INSERT INTO plantillas_proveedores
                                 (proveedor_marca, col_codigo, col_descripcion, col_costo, col_contenido_caja)
                                 VALUES (?, ?, ?, ?, ?)
                                 ON CONFLICT(proveedor_marca) DO UPDATE SET
                                 col_codigo=excluded.col_codigo, col_descripcion=excluded.col_descripcion,
                                 col_costo=excluded.col_costo, col_contenido_caja=excluded.col_contenido_caja''',
                              (train_marca, map_cod, map_desc, map_neto, map_caja))
                    conn.commit()
                    st.success(f"¡Plantilla para {train_marca} guardada!")
                except Exception as e:
                    st.error(f"Error guardando: {e}")
                finally:
                    conn.close()

    # ---------------- MAIN UI: INGESTA MASIVA Y RESILIENTE ----------------
    st.title("Ingesta Masiva y Extracción Resiliente (Barter Plus)")

    st.subheader("1. Procesamiento Masivo")
    col1, col2 = st.columns(2)

    with col1:
        update_file = st.file_uploader("Sube Lista Nueva (Excel o PDF)", type=["xlsx", "xls", "pdf"], key="update_file")
    with col2:
        conn = get_connection()
        df_templates = pd.read_sql_query("SELECT proveedor_marca FROM plantillas_proveedores", conn)
        conn.close()

        marcas_guardadas = df_templates['proveedor_marca'].tolist() if not df_templates.empty else []
        marca_update = st.selectbox("Selecciona la Marca/Plantilla para Procesar:", ["-- Seleccionar --"] + marcas_guardadas)

    if update_file and marca_update != "-- Seleccionar --":
        if st.button("Procesar Lista"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT col_codigo, col_descripcion, col_costo, col_contenido_caja FROM plantillas_proveedores WHERE proveedor_marca = ?", (marca_update,))
            tpl_row = c.fetchone()
            conn.close()

            if tpl_row:
                template = {
                    'col_codigo': tpl_row[0],
                    'col_descripcion': tpl_row[1],
                    'col_costo': tpl_row[2],
                    'col_contenido_caja': tpl_row[3]
                }

                with st.spinner("Purgando metadata, disclaimers y extrayendo bloques comerciales..."):
                    blocks, total_omitted = process_file_advanced(update_file)

                if blocks:
                    total_ins, total_upd, total_ign = 0, 0, 0
                    global_report = []

                    with st.spinner(f"Bloques detectados: {len(blocks)}. Aplicando plantilla y Matching Fuzzy..."):
                        for block in blocks:
                            ins, upd, ign, rep = process_mass_update(block, marca_update, template)
                            total_ins += ins
                            total_upd += upd
                            total_ign += ign
                            global_report.extend(rep)

                        st.session_state['process_report'] = {
                            'omitted': total_omitted + total_ign,
                            'inserted': total_ins,
                            'updated': total_upd,
                            'details': global_report
                        }
                        st.success(f"✅ ¡Proceso completado para {marca_update}!")
                else:
                    st.error("El Módulo de Purga descartó el archivo entero por no detectar tablas comerciales válidas.")

    st.write("---")
    st.subheader("2. Reporte de Proceso")
    if 'process_report' in st.session_state:
        rep = st.session_state['process_report']
        st.info(f"📊 Resumen: {rep['inserted']} Productos Nuevos | {rep['updated']} Actualizados | {rep['omitted']} Filas Purgadas/Omitidas (Basura o Incompletas)")
        if rep['details']:
            df_rep = pd.DataFrame(rep['details'])
            st.dataframe(df_rep, use_container_width=True)

    st.write("---")
    st.subheader("3. Inventario Maestro Unificado")

    conn = get_connection()
    df_maestro = pd.read_sql_query("SELECT sku_interno, codigo_proveedor, descripcion, marca, tipo_venta, capacidad_medida, contenido_caja, costo_actual, fecha_actualizacion FROM productos_maestro", conn)
    conn.close()

    st.dataframe(df_maestro, use_container_width=True, hide_index=True)

    if not df_maestro.empty:
        st.download_button(
            label="📥 Exportar Inventario Maestro (Excel)",
            data=to_excel(df_maestro),
            file_name='INVENTARIO_MAESTRO_COMPLETO.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

if __name__ == '__main__':
    main()
