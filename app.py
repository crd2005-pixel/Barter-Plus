import streamlit as st
import sqlite3
import pandas as pd
import pdfplumber
import re
from datetime import datetime
from thefuzz import fuzz
import io

DB_NAME = "master_data.db"

@st.cache_resource
def run_init_db():
    init_db()

def init_db():
    """
    Base de Datos Resiliente y Auto-Corregible.
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

    # Tabla Plantillas Avanzadas (Mapeamos por 'nombre_plantilla' ya que un proveedor puede usar un excel que sirva para varias marcas/pestañas)
    c.execute('''
        CREATE TABLE IF NOT EXISTS plantillas_proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_plantilla TEXT UNIQUE,
            col_codigo TEXT,
            col_descripcion TEXT,
            col_costo TEXT,
            col_contenido_caja TEXT,
            col_presentacion TEXT
        )
    ''')

    # Módulo de Auto-Corrección: Inspección física del esquema de productos_maestro
    c.execute("PRAGMA table_info(productos_maestro)")
    columns = [info[1] for info in c.fetchall()]

    required_columns = {
        'sku_interno': 'TEXT UNIQUE',
        'tipo_venta': 'TEXT',
        'capacidad_medida': 'TEXT',
        'contenido_caja': 'TEXT'
    }

    for col, dtype in required_columns.items():
        if col not in columns:
            try:
                c.execute(f"ALTER TABLE productos_maestro ADD COLUMN {col} {dtype}")
                st.toast(f"🛠️ Autocorrección de BD: Columna '{col}' agregada a productos_maestro.", icon="🔧")
            except sqlite3.OperationalError as e:
                # Fallback genérico para constraints UNIQUE complejos en versiones viejas de SQLite
                if 'UNIQUE' in dtype:
                   c.execute(f"ALTER TABLE productos_maestro ADD COLUMN {col} TEXT")
                else:
                    raise e

    # Auto-Corrección para plantillas_proveedores
    c.execute("PRAGMA table_info(plantillas_proveedores)")
    template_cols = [info[1] for info in c.fetchall()]

    req_template_cols = {
        'col_contenido_caja': 'TEXT',
        'col_presentacion': 'TEXT'
    }

    for col, dtype in req_template_cols.items():
        if col not in template_cols:
            c.execute(f"ALTER TABLE plantillas_proveedores ADD COLUMN {col} {dtype}")
            st.toast(f"🛠️ Autocorrección de BD: Columna '{col}' agregada a plantillas_proveedores.", icon="🔧")

    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_NAME)

def purge_dataframe(df):
    """
    Purga Operativa Total (Pre-Mapeo).
    Descarta filas 100% vacías, encabezados operativos repetidos, y disclaimers.
    """
    if df is None or df.empty:
        return df

    # Limpieza Vertical Total
    df = df.replace(r'^\s*$', pd.NA, regex=True)
    df = df.dropna(how='all')

    if df.empty:
        return df

    rows_to_keep = []

    # Regex Patterns para descartes
    header_pattern = re.compile(r'\b(CÓDIGO|CODIGO|DESCRIPCIÓN|DESCRIPCION|NETO|PRECIO LISTA|PRECIO|PRODUCTO|FILTROS|ACEITES|ARTICULO|ARTÍCULO|MARCA)\b', re.IGNORECASE)
    disclaimer_pattern = re.compile(r'(LISTA SUJETA A CAMBIOS|NO INCLUYE IVA|VÁLIDA HASTA|VALIDA HASTA|CONFIRMAR PRECIOS|PAGINA \d+|PÁGINA \d+|SOLO CONTADO|LOS PRECIOS)', re.IGNORECASE)

    for index, row in df.iterrows():
        row_str = " ".join([str(val) for val in row if pd.notna(val)])

        # Filtrar disclaimers
        if disclaimer_pattern.search(row_str):
            continue

        # Filtrar encabezados excesivos (>50% de celdas válidas)
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

    # Reindexar y asignar nombres únicos de columna (evita problemas de PyArrow)
    purged_df = df.loc[rows_to_keep].reset_index(drop=True)
    purged_df.columns = [f"Col_{i}" for i in range(len(purged_df.columns))]
    return purged_df

def detect_unit_and_capacity(description, presentacion_adicional=None):
    """
    Detección Inteligente de Unidades (Regex).
    """
    desc_upper = str(description).upper()
    if pd.notna(presentacion_adicional):
        desc_upper += " " + str(presentacion_adicional).upper()

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
    marca_prefix = marca[:3].upper() if len(marca) >= 3 else marca.upper().ljust(3, 'X')
    tipo_code = "UN" if tipo_venta == "UNIDAD" else "GR"
    return f"{marca_prefix}-{tipo_code}-{str(item_id).zfill(5)}"

def extract_excel_sheets(uploaded_file):
    """
    Extrae un diccionario de {nombre_hoja: DataFrame_Purgado}
    """
    try:
        xl = pd.ExcelFile(uploaded_file)
        sheets_data = {}
        for sheet_name in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet_name, header=None)
            df_purged = purge_dataframe(df)
            if not df_purged.empty:
                sheets_data[sheet_name] = df_purged
        return sheets_data
    except Exception as e:
        st.error(f"Error procesando el Excel: {e}")
        return {}

def extract_pdf_data(uploaded_file):
    """
    Extrae, purga y retorna DataFrame de PDF.
    """
    try:
        data = []
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    data.extend(table)
        if data:
            df = pd.DataFrame(data)
            return purge_dataframe(df)
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error procesando el PDF: {e}")
        return pd.DataFrame()

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
    Actualización y Unificación Masiva cruzando por Marca (Dinámica) y Tipo de Venta.
    """
    col_codigo = template['col_codigo']
    col_desc = template['col_descripcion']
    col_costo = template['col_costo']
    col_caja = template['col_contenido_caja']
    col_pres = template['col_presentacion']

    none_option = "[Ninguno (No Existe)]"

    conn = get_connection()
    c = conn.cursor()

    # Extraer de BD filtrando estrictamente por Marca (Automática por hoja de Excel o Manual en PDF)
    c.execute("SELECT id, codigo_proveedor, descripcion, tipo_venta FROM productos_maestro WHERE marca = ?", (marca,))
    db_items = c.fetchall()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updates = 0
    inserts = 0

    for _, row in df.iterrows():
        cod_prov = str(row[col_codigo]).strip() if col_codigo != none_option and col_codigo in df.columns and pd.notna(row[col_codigo]) else ""
        desc = str(row[col_desc]).strip() if col_desc != none_option and col_desc in df.columns and pd.notna(row[col_desc]) else ""
        costo = clean_currency(row[col_costo]) if col_costo != none_option and col_costo in df.columns else 0.0

        caja = clean_box_content(row[col_caja]) if col_caja != none_option and col_caja in df.columns else "1"
        pres = str(row[col_pres]).strip() if col_pres != none_option and col_pres in df.columns and pd.notna(row[col_pres]) else ""

        if not desc or desc.lower() in ['nan', 'none', '']:
            continue

        tipo_venta, capacidad = detect_unit_and_capacity(desc, presentacion_adicional=pres)
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

            # Umbral de similitud del 85%
            if best_score >= 85:
                matched_id = best_id

        if matched_id:
            c.execute('''UPDATE productos_maestro
                         SET costo_actual = ?, fecha_actualizacion = ?, contenido_caja = ?, capacidad_medida = ?
                         WHERE id = ?''', (costo, now, caja, capacidad, matched_id))
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
            inserts += 1

    conn.commit()
    conn.close()

    return inserts, updates

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario Maestro')
    return output.getvalue()


def main():
    st.set_page_config(page_title="Barter Plus - Ingesta Avanzada", layout="wide")
    st.title("Sistema Avanzado de Ingesta y Mapeo Masivo (Barter Plus)")

    run_init_db()

    tab1, tab2, tab3 = st.tabs(["1. Gestión de Plantillas Avanzadas", "2. Actualización Masiva", "3. Inventario Maestro Unificado"])

    none_option = "[Ninguno (No Existe)]"

    # ---------------- TAB 1: GESTIÓN DE PLANTILLAS AVANZADAS ----------------
    with tab1:
        st.header("Entrenamiento de Plantilla de Mapeo Avanzado")
        st.info("Define cómo extraer columnas de un proveedor. El Módulo Operativo purgará basura automáticamente.")

        train_file = st.file_uploader("Sube lista de ejemplo (Excel/PDF)", type=["xlsx", "xls", "pdf"], key="train_file")
        nombre_plantilla = st.text_input("Nombre de la Plantilla (Ej: Proveedor Distribuidor Sur)", key="train_plantilla").strip().upper()

        if train_file and nombre_plantilla:
            if st.button("Analizar y Purgar", key="btn_analizar"):
                filename = train_file.name.lower()

                df_train = None

                # Para entrenar, si es excel, usamos solo la primera hoja purgada para mostrarle al usuario las columnas.
                if filename.endswith(('.xls', '.xlsx')):
                    sheets_data = extract_excel_sheets(train_file)
                    if sheets_data:
                        first_sheet = list(sheets_data.keys())[0]
                        df_train = sheets_data[first_sheet]
                        st.info(f"Para el entrenamiento se está previsualizando la hoja: '{first_sheet}'")
                elif filename.endswith('.pdf'):
                    df_train = extract_pdf_data(train_file)

                if df_train is not None and not df_train.empty:
                    st.session_state['df_train'] = df_train
                    st.success("✅ Archivo leído y purgado exitosamente.")
                else:
                    st.error("No se extrajeron datos válidos tras la purga. Revisa el archivo.")

            if 'df_train' in st.session_state:
                df_train = st.session_state['df_train']
                st.write("### Vista previa de la Estructura (Purgada):")
                st.dataframe(df_train.head(10))

                cols_available = [none_option] + list(df_train.columns)

                st.write("### Configuración de Mapeo Avanzado")
                col1, col2 = st.columns(2)
                with col1:
                    sel_cod = st.selectbox("Código de Proveedor", cols_available, key="map_cod")
                    sel_desc = st.selectbox("Descripción Principal *", [c for c in cols_available if c != none_option], key="map_desc")
                    sel_costo = st.selectbox("Costo Actual / Precio", cols_available, key="map_costo")
                with col2:
                    sel_caja = st.selectbox("Contenido por Caja (Cantidad)", cols_available, key="map_caja")
                    sel_pres = st.selectbox("Presentación Adicional (Unidad/Litros)", cols_available, key="map_pres")

                if st.button("Guardar Plantilla de Mapeo"):
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute('''INSERT INTO plantillas_proveedores
                                     (nombre_plantilla, col_codigo, col_descripcion, col_costo, col_contenido_caja, col_presentacion)
                                     VALUES (?, ?, ?, ?, ?, ?)
                                     ON CONFLICT(nombre_plantilla) DO UPDATE SET
                                     col_codigo=excluded.col_codigo, col_descripcion=excluded.col_descripcion,
                                     col_costo=excluded.col_costo, col_contenido_caja=excluded.col_contenido_caja,
                                     col_presentacion=excluded.col_presentacion''',
                                  (nombre_plantilla, sel_cod, sel_desc, sel_costo, sel_caja, sel_pres))
                        conn.commit()
                        st.success(f"Plantilla '{nombre_plantilla}' guardada/actualizada con éxito.")
                    except Exception as e:
                        st.error(f"Error guardando plantilla: {e}")
                    finally:
                        conn.close()

    # ---------------- TAB 2: ACTUALIZACIÓN MASIVA DE LOTES ----------------
    with tab2:
        st.header("Actualización Masiva y Auto-Asignación de Marca")
        st.info("Sube un archivo. Si es Excel, procesará TODAS las pestañas y asignará automáticamente el nombre de la pestaña como MARCA. Si es PDF, se te pedirá ingresar la Marca.")

        conn = get_connection()
        df_templates = pd.read_sql_query("SELECT nombre_plantilla FROM plantillas_proveedores", conn)
        conn.close()

        if df_templates.empty:
            st.warning("Aún no hay plantillas. Ve a la Pestaña 1.")
        else:
            plantillas_guardadas = df_templates['nombre_plantilla'].tolist()
            plantilla_update = st.selectbox("Selecciona la Plantilla a utilizar", ["-- Seleccionar --"] + plantillas_guardadas)

            update_file = st.file_uploader("Sube lista masiva (Excel/PDF)", type=["xlsx", "xls", "pdf"], key="update_file")

            if update_file and plantilla_update != "-- Seleccionar --":
                filename = update_file.name.lower()

                marca_manual_pdf = None
                if filename.endswith('.pdf'):
                     marca_manual_pdf = st.text_input("Ingresa la MARCA (Requerido para PDFs):", key="marca_pdf").strip().upper()

                if st.button("Procesar Lista Masivamente"):
                    if filename.endswith('.pdf') and not marca_manual_pdf:
                        st.error("Debes ingresar la Marca para procesar un PDF.")
                        st.stop()

                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("SELECT col_codigo, col_descripcion, col_costo, col_contenido_caja, col_presentacion FROM plantillas_proveedores WHERE nombre_plantilla = ?", (plantilla_update,))
                    template_row = c.fetchone()
                    conn.close()

                    if template_row:
                        template = {
                            'col_codigo': template_row[0],
                            'col_descripcion': template_row[1],
                            'col_costo': template_row[2],
                            'col_contenido_caja': template_row[3],
                            'col_presentacion': template_row[4]
                        }

                        total_ins = 0
                        total_upd = 0

                        if filename.endswith(('.xls', '.xlsx')):
                            with st.spinner("Procesando Excel Multi-Pestañas en lote..."):
                                sheets_data = extract_excel_sheets(update_file)

                                if not sheets_data:
                                    st.error("No se extrajeron datos válidos (archivo vacío tras purga).")
                                else:
                                    for sheet_name, df_update in sheets_data.items():
                                        # AUTO-ASIGNACIÓN DE MARCA POR NOMBRE DE PESTAÑA
                                        marca_lote = sheet_name.strip().upper()
                                        ins, upd = process_mass_update(df_update, marca_lote, template)
                                        total_ins += ins
                                        total_upd += upd
                                        st.write(f"✔️ Hoja '{sheet_name}' (Marca: {marca_lote}) procesada: {ins} insertados, {upd} actualizados.")

                                    st.success(f"✅ ¡Procesamiento Masivo Multi-Pestañas Completado! Total Insertados: {total_ins} | Total Actualizados: {total_upd}")

                        elif filename.endswith('.pdf'):
                            with st.spinner("Procesando PDF..."):
                                df_update = extract_pdf_data(update_file)
                                if not df_update.empty:
                                    ins, upd = process_mass_update(df_update, marca_manual_pdf, template)
                                    st.success(f"✅ ¡PDF procesado! Marca: {marca_manual_pdf}. Insertados: {ins} | Actualizados: {upd}")
                                else:
                                    st.error("El PDF está vacío tras la purga operativa.")

    # ---------------- TAB 3: INVENTARIO MAESTRO UNIFICADO ----------------
    with tab3:
        st.header("Inventario Maestro Unificado (Consolidado)")

        conn = get_connection()
        df_maestro = pd.read_sql_query("SELECT * FROM productos_maestro", conn)
        conn.close()

        st.dataframe(df_maestro, use_container_width=True)

        if not df_maestro.empty:
            excel_data = to_excel(df_maestro)
            st.download_button(
                label="📥 Exportar Base de Datos Maestra (Excel)",
                data=excel_data,
                file_name='master_data_barterplus.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
        else:
            st.info("La Base de Datos Maestra está vacía.")

if __name__ == '__main__':
    main()
