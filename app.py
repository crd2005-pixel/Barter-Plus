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
    Modulo "Parser Avanzado" (Purga + Bloques Comerciales)
    Primero blinda el DataFrame forzando nombres únicos.
    Usa Regex para descartar avisos, IVA, y separar en bloques si hay cambios bruscos.
    Retorna una lista de DataFrames purgados (los "bloques comerciales").
    """
    if df is None or df.empty:
        return []

    # 1. Blindar el DataFrame
    df.columns = [f"Col_{i}" for i in range(len(df.columns))]

    # 2. Limpieza de Vacíos
    df = df.replace(r'^\s*$', pd.NA, regex=True)
    df = df.dropna(how='all')
    if df.empty:
        return []

    # Regex para basura y disclaimers
    disclaimer_pattern = re.compile(r'(LISTA SUJETA A CAMBIOS|NO INCLUYE IVA|VÁLIDA HASTA|VALIDA HASTA|CONFIRMAR PRECIOS|PAGINA \d+|SOLO CONTADO|RAMONSABIO|RAMON SABIO)', re.IGNORECASE)

    # Regex para detectar nuevas cabeceras (cambio brusco de estructura / nuevo bloque)
    header_pattern = re.compile(r'\b(CÓDIGO|CODIGO|DESCRIPCIÓN|DESCRIPCION|NETO|PRECIO|PRODUCTO)\b', re.IGNORECASE)

    blocks = []
    current_block_rows = []

    for index, row in df.iterrows():
        row_str = " ".join([str(val) for val in row if pd.notna(val)])

        # Filtro de disclaimers
        if disclaimer_pattern.search(row_str):
            continue

        # Detectar si esta fila es una nueva cabecera (más de 1 celda coincide)
        header_matches = sum(1 for val in row if pd.notna(val) and header_pattern.search(str(val)))

        # Si encontramos una cabecera nueva, cortamos el bloque anterior
        if header_matches >= 2:
            if current_block_rows:
                blocks.append(pd.DataFrame(current_block_rows, columns=df.columns))
                current_block_rows = []
            continue # Descartamos la fila de cabecera operativa

        current_block_rows.append(row)

    # Añadir el último bloque
    if current_block_rows:
        blocks.append(pd.DataFrame(current_block_rows, columns=df.columns))

    return [block.reset_index(drop=True) for block in blocks if not block.empty]

def detect_unit_and_capacity(description):
    """
    Clasifica automáticamente el Tipo_Venta (UNIDAD o GRANEL).
    """
    desc_upper = str(description).upper()
    tipo_venta = "UNIDAD"

    match_granel = re.search(r'\b(TAMBOR|TBR|200\s*L|GRANEL|BALDE|20\s*L)\b', desc_upper)
    if match_granel:
        tipo_venta = "GRANEL"

    return tipo_venta

def generate_sku(marca, tipo_venta, item_id):
    """
    Generador de SKU Propio Unificado: [MARCA]-[UN/GR]-[ID_AUTONUMERICO]
    """
    marca_prefix = marca[:3].upper() if len(marca) >= 3 else marca.upper().ljust(3, 'X')
    tipo_code = "UN" if tipo_venta == "GRANEL" else "UN"
    if tipo_venta == "GRANEL":
        tipo_code = "GR"
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

def process_mass_update(df_blocks, marca, template):
    """
    Procesa múltiples bloques comerciales (DataFrames purgados).
    Cruza por Marca y Tipo de Venta.
    """
    col_codigo = template['col_codigo']
    col_desc = template['col_descripcion']
    col_costo = template['col_costo']
    col_caja = template.get('col_contenido_caja', NONE_OPTION)

    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT id, codigo_proveedor, descripcion, tipo_venta FROM productos_maestro WHERE marca = ?", (marca,))
    db_items = c.fetchall()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updates = 0
    inserts = 0

    for df in df_blocks:
        for _, row in df.iterrows():
            cod_prov = str(row[col_codigo]).strip() if col_codigo != NONE_OPTION and col_codigo in df.columns and pd.notna(row[col_codigo]) else ""
            desc = str(row[col_desc]).strip() if col_desc != NONE_OPTION and col_desc in df.columns and pd.notna(row[col_desc]) else ""
            costo = clean_currency(row[col_costo]) if col_costo != NONE_OPTION and col_costo in df.columns else 0.0
            caja = clean_box_content(row[col_caja]) if col_caja != NONE_OPTION and col_caja in df.columns else "1"

            if not desc or desc.lower() in ['nan', 'none', '']:
                continue

            tipo_venta = detect_unit_and_capacity(desc)
            matched_id = None

            # 1. Match Exacto por Código Proveedor y Tipo de Venta
            if cod_prov and cod_prov.lower() not in ['nan', 'none']:
                for item in db_items:
                    if item[1] == cod_prov and item[3] == tipo_venta:
                        matched_id = item[0]
                        break

            # 2. Match Fuzzy Inteligente (Aislado por bloque gracias al Parser Avanzado)
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
                             SET costo_actual = ?, fecha_actualizacion = ?, contenido_caja = ?
                             WHERE id = ?''', (costo, now, caja, matched_id))
                updates += 1
            else:
                c.execute('''INSERT INTO productos_maestro
                             (codigo_proveedor, descripcion, marca, tipo_venta, contenido_caja, costo_actual, fecha_actualizacion)
                             VALUES (?, ?, ?, ?, ?, ?, ?)''',
                             (cod_prov, desc, marca, tipo_venta, caja, costo, now))
                new_id = c.lastrowid
                sku = generate_sku(marca, tipo_venta, new_id)
                c.execute("UPDATE productos_maestro SET sku_interno = ? WHERE id = ?", (sku, new_id))

                db_items.append((new_id, cod_prov, desc, tipo_venta))
                inserts += 1

    conn.commit()
    conn.close()

    return inserts, updates

def parse_raw_file(uploaded_file):
    filename = uploaded_file.name.lower()
    try:
        if filename.endswith(('.xls', '.xlsx')):
            xl = pd.ExcelFile(uploaded_file)
            # Retorna el crudo de la primera hoja para la vista de entrenamiento
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
    filename = uploaded_file.name.lower()
    blocks_all = []
    try:
        if filename.endswith(('.xls', '.xlsx')):
            xl = pd.ExcelFile(uploaded_file)
            for sheet in xl.sheet_names:
                df = pd.read_excel(xl, sheet_name=sheet, header=None)
                blocks_all.extend(purge_dataframe_advanced(df))
        elif filename.endswith('.pdf'):
            data = []
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        data.extend(table)
            if data:
                df = pd.DataFrame(data)
                blocks_all.extend(purge_dataframe_advanced(df))
    except Exception as e:
        st.error(f"Error en Parser Avanzado: {e}")
    return blocks_all

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario Maestro')
    return output.getvalue()


def main():
    st.set_page_config(page_title="Gestor Resiliente y Entrenable", layout="wide")

    run_init_db()

    # ---------------- SIDEBAR: INTELIGENCIA DE MAPEO GUIADO ----------------
    with st.sidebar:
        st.header("Gestión de Plantillas (Mapeo)")
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

    # ---------------- MAIN UI: INGESTA MINIMALISTA ----------------
    st.title("Sistema de Extracción Robusta e Ingesta")

    st.subheader("1. Ingesta Masiva")
    col1, col2 = st.columns(2)

    with col1:
        update_file = st.file_uploader("Sube Lista Nueva (Excel o PDF)", type=["xlsx", "xls", "pdf"], key="update_file")
    with col2:
        conn = get_connection()
        df_templates = pd.read_sql_query("SELECT proveedor_marca FROM plantillas_proveedores", conn)
        conn.close()

        marcas_guardadas = df_templates['proveedor_marca'].tolist() if not df_templates.empty else []
        marca_update = st.selectbox("Selecciona la Marca/Proveedor", ["-- Seleccionar --"] + marcas_guardadas)

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

                with st.spinner("Parser Avanzado detectando bloques comerciales y purgando metadata..."):
                    blocks = process_file_advanced(update_file)

                if blocks:
                    with st.spinner(f"Bloques detectados: {len(blocks)}. Ejecutando Inteligencia de Matching..."):
                        ins, upd = process_mass_update(blocks, marca_update, template)
                        st.success(f"✅ ¡Completado! Marca: {marca_update}. Creados: {ins} | Actualizados: {upd}")
                else:
                    st.error("El Parser Avanzado descartó el archivo entero por no detectar bloques comerciales válidos.")

    st.write("---")
    st.subheader("2. Inventario Maestro Unificado")

    conn = get_connection()
    df_maestro = pd.read_sql_query("SELECT sku_interno, codigo_proveedor, descripcion, marca, tipo_venta, contenido_caja, costo_actual, fecha_actualizacion FROM productos_maestro", conn)
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
