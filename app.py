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

    # Librería de Plantillas (Heterogénea)
    c.execute('''
        CREATE TABLE IF NOT EXISTS plantillas_proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_plantilla TEXT UNIQUE,
            num_columnas INTEGER,
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
                if 'UNIQUE' in dtype:
                   c.execute(f"ALTER TABLE productos_maestro ADD COLUMN {col} TEXT")
                else:
                    raise e

    # Auto-Corrección para plantillas_proveedores
    c.execute("PRAGMA table_info(plantillas_proveedores)")
    template_cols = [info[1] for info in c.fetchall()]

    req_template_cols = {
        'num_columnas': 'INTEGER',
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
    Descarta filas vacías, encabezados operativos repetidos, y disclaimers.
    Blinda el DataFrame forzando nombres únicos (Col_0, Col_1, etc.).
    """
    if df is None or df.empty:
        return df

    # Limpieza Vertical Total
    df = df.replace(r'^\s*$', pd.NA, regex=True)
    df = df.dropna(how='all')

    if df.empty:
        return df

    rows_to_keep = []

    header_pattern = re.compile(r'\b(CÓDIGO|CODIGO|DESCRIPCIÓN|DESCRIPCION|NETO|PRECIO LISTA|PRECIO|PRODUCTO|FILTROS|ACEITES|ARTICULO|ARTÍCULO|MARCA)\b', re.IGNORECASE)
    disclaimer_pattern = re.compile(r'(LISTA SUJETA A CAMBIOS|NO INCLUYE IVA|VÁLIDA HASTA|VALIDA HASTA|CONFIRMAR PRECIOS|PAGINA \d+|PÁGINA \d+|SOLO CONTADO|LOS PRECIOS)', re.IGNORECASE)

    for index, row in df.iterrows():
        row_str = " ".join([str(val) for val in row if pd.notna(val)])

        if disclaimer_pattern.search(row_str):
            continue

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

def match_template(num_cols):
    """
    Motor de Ingesta HETEROGÉNEAS:
    Intenta buscar una plantilla en la librería cuyo número de columnas coincida con la pestaña purgada.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT nombre_plantilla, col_codigo, col_descripcion, col_costo, col_contenido_caja, col_presentacion
                 FROM plantillas_proveedores
                 WHERE num_columnas = ? LIMIT 1''', (num_cols,))
    row = c.fetchone()
    conn.close()

    if row:
        return {
            'nombre_plantilla': row[0],
            'col_codigo': row[1],
            'col_descripcion': row[2],
            'col_costo': row[3],
            'col_contenido_caja': row[4],
            'col_presentacion': row[5]
        }
    return None

def process_mass_update(df, marca, template):
    """
    Actualización y Unificación Masiva cruzando por Marca (Dinámica) y Tipo de Venta.
    Retorna un histórico (reporte_operativo) de lo modificado/insertado.
    """
    col_codigo = template['col_codigo']
    col_desc = template['col_descripcion']
    col_costo = template['col_costo']
    col_caja = template['col_contenido_caja']
    col_pres = template['col_presentacion']

    none_option = "[Ninguno (No Existe)]"

    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT id, codigo_proveedor, descripcion, tipo_venta FROM productos_maestro WHERE marca = ?", (marca,))
    db_items = c.fetchall()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    reporte_operativo = []

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

            if best_score >= 85:
                matched_id = best_id

        if matched_id:
            c.execute('''UPDATE productos_maestro
                         SET costo_actual = ?, fecha_actualizacion = ?, contenido_caja = ?, capacidad_medida = ?
                         WHERE id = ?''', (costo, now, caja, capacidad, matched_id))

            # Recuperar SKU para el reporte
            c.execute("SELECT sku_interno FROM productos_maestro WHERE id = ?", (matched_id,))
            sku_row = c.fetchone()
            sku_val = sku_row[0] if sku_row else ""

            reporte_operativo.append({
                'Acción': 'Actualizado',
                'SKU Propio': sku_val,
                'Marca': marca,
                'Descripción': desc,
                'Tipo': tipo_venta,
                'Costo': costo
            })
        else:
            c.execute('''INSERT INTO productos_maestro
                         (codigo_proveedor, descripcion, marca, tipo_venta, capacidad_medida, contenido_caja, costo_actual, fecha_actualizacion)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                         (cod_prov, desc, marca, tipo_venta, capacidad, caja, costo, now))
            new_id = c.lastrowid
            sku = generate_sku(marca, tipo_venta, new_id)
            c.execute("UPDATE productos_maestro SET sku_interno = ? WHERE id = ?", (sku, new_id))

            db_items.append((new_id, cod_prov, desc, tipo_venta))
            reporte_operativo.append({
                'Acción': 'NUEVO',
                'SKU Propio': sku,
                'Marca': marca,
                'Descripción': desc,
                'Tipo': tipo_venta,
                'Costo': costo
            })

    conn.commit()
    conn.close()

    return reporte_operativo

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario Maestro')
    return output.getvalue()


def main():
    st.set_page_config(page_title="Barter Plus - Ingesta Avanzada", layout="wide")
    st.title("Sistema Avanzado HETEROGÉNEO de Ingesta (Barter Plus)")

    run_init_db()

    # UI Sidebar: Inventario Maestro Unificado
    st.sidebar.header("Inventario Maestro Unificado")
    conn = get_connection()
    df_maestro = pd.read_sql_query("SELECT sku_interno, descripcion, marca, tipo_venta, capacidad_medida, contenido_caja, costo_actual FROM productos_maestro", conn)
    conn.close()
    st.sidebar.dataframe(df_maestro)
    if not df_maestro.empty:
        st.sidebar.download_button(
            label="📥 Exportar Maestra a Excel",
            data=to_excel(df_maestro),
            file_name='master_data_barterplus.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    tab1, tab2, tab3 = st.tabs(["1. Gestión de Librería de Plantillas", "2. Actualización Masiva", "3. Reporte Visual y Exportación"])

    none_option = "[Ninguno (No Existe)]"

    # ---------------- TAB 1: GESTIÓN DE LIBRERÍA DE PLANTILLAS ----------------
    with tab1:
        st.header("Entrenamiento de Librería de Plantillas (Heterogénea)")
        st.info("Guarda la estructura (número de columnas post-purga) asociada a un nombre para que el motor la detecte automáticamente.")

        train_file = st.file_uploader("Sube lista de ejemplo (Excel/PDF)", type=["xlsx", "xls", "pdf"], key="train_file")
        nombre_plantilla = st.text_input("Nombre de la Plantilla (Ej: Formato_Ramon_Sabio)", key="train_plantilla").strip()

        if train_file and nombre_plantilla:
            if st.button("Analizar y Purgar", key="btn_analizar"):
                filename = train_file.name.lower()
                df_train = None

                if filename.endswith(('.xls', '.xlsx')):
                    sheets_data = extract_excel_sheets(train_file)
                    if sheets_data:
                        first_sheet = list(sheets_data.keys())[0]
                        df_train = sheets_data[first_sheet]
                        st.info(f"Previsualizando la hoja: '{first_sheet}' para generar la plantilla.")
                elif filename.endswith('.pdf'):
                    df_train = extract_pdf_data(train_file)

                if df_train is not None and not df_train.empty:
                    st.session_state['df_train'] = df_train
                    st.success("✅ Archivo purgado. El motor usará la cantidad de columnas para identificar esta estructura.")
                else:
                    st.error("No se extrajeron datos válidos.")

            if 'df_train' in st.session_state:
                df_train = st.session_state['df_train']
                num_columnas = len(df_train.columns)
                st.write(f"### Vista previa de la Estructura (Columnas purgadas: {num_columnas})")
                st.dataframe(df_train.head(10))

                cols_available = [none_option] + list(df_train.columns)

                st.write("### Configuración de Mapeo")
                col1, col2 = st.columns(2)
                with col1:
                    sel_cod = st.selectbox("Código de Proveedor", cols_available, key="map_cod")
                    sel_desc = st.selectbox("Descripción Principal *", [c for c in cols_available if c != none_option], key="map_desc")
                    sel_costo = st.selectbox("Costo Actual / Precio", cols_available, key="map_costo")
                with col2:
                    sel_caja = st.selectbox("Contenido por Caja (Cantidad)", cols_available, key="map_caja")
                    sel_pres = st.selectbox("Presentación Adicional (Unidad/Litros)", cols_available, key="map_pres")

                if st.button("Guardar Plantilla en la Librería"):
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute('''INSERT INTO plantillas_proveedores
                                     (nombre_plantilla, num_columnas, col_codigo, col_descripcion, col_costo, col_contenido_caja, col_presentacion)
                                     VALUES (?, ?, ?, ?, ?, ?, ?)
                                     ON CONFLICT(nombre_plantilla) DO UPDATE SET
                                     num_columnas=excluded.num_columnas, col_codigo=excluded.col_codigo, col_descripcion=excluded.col_descripcion,
                                     col_costo=excluded.col_costo, col_contenido_caja=excluded.col_contenido_caja,
                                     col_presentacion=excluded.col_presentacion''',
                                  (nombre_plantilla, num_columnas, sel_cod, sel_desc, sel_costo, sel_caja, sel_pres))
                        conn.commit()
                        st.success(f"Plantilla '{nombre_plantilla}' guardada en la Librería.")
                    except Exception as e:
                        st.error(f"Error guardando plantilla: {e}")
                    finally:
                        conn.close()

    # ---------------- TAB 2: ACTUALIZACIÓN MASIVA HETEROGÉNEA ----------------
    with tab2:
        st.header("Actualización Masiva (Librería Automática)")
        st.info("Sube un Excel. El Motor evaluará cada pestaña por separado, buscará una plantilla compatible en tu Librería basándose en la estructura, purgará y extraerá heredando la Marca de la pestaña. Zero Adivinanza.")

        update_file = st.file_uploader("Sube lista masiva (Excel/PDF)", type=["xlsx", "xls", "pdf"], key="update_file")

        if update_file:
            filename = update_file.name.lower()

            marca_manual_pdf = None
            plantilla_pdf = None

            if filename.endswith('.pdf'):
                marca_manual_pdf = st.text_input("Ingresa la MARCA (Requerido para PDFs):", key="marca_pdf").strip().upper()

                conn = get_connection()
                df_templates = pd.read_sql_query("SELECT nombre_plantilla FROM plantillas_proveedores", conn)
                conn.close()
                if not df_templates.empty:
                    plantillas_guardadas = df_templates['nombre_plantilla'].tolist()
                    plantilla_pdf = st.selectbox("Selecciona la Plantilla (Requerido para PDF):", ["-- Seleccionar --"] + plantillas_guardadas)

            if st.button("Procesar Lista Masivamente"):
                if filename.endswith('.pdf') and (not marca_manual_pdf or plantilla_pdf == "-- Seleccionar --"):
                    st.error("Debes ingresar la Marca y seleccionar la plantilla para procesar un PDF.")
                    st.stop()

                global_report = []

                if filename.endswith(('.xls', '.xlsx')):
                    with st.spinner("Procesando Multi-Pestañas Heterogéneas..."):
                        sheets_data = extract_excel_sheets(update_file)

                        if not sheets_data:
                            st.error("No se extrajeron datos válidos.")
                        else:
                            for sheet_name, df_update in sheets_data.items():
                                marca_lote = sheet_name.strip().upper()
                                num_cols = len(df_update.columns)

                                template = match_template(num_cols)

                                if template:
                                    st.write(f"🔍 Hoja '{sheet_name}': Match con Plantilla '{template['nombre_plantilla']}' ({num_cols} columnas).")
                                    repo = process_mass_update(df_update, marca_lote, template)
                                    global_report.extend(repo)
                                else:
                                    st.warning(f"⚠️ Hoja '{sheet_name}': Omitida. No hay plantilla en la Librería para una estructura de {num_cols} columnas.")

                            st.session_state['global_report'] = global_report
                            st.success("✅ Procesamiento completado. Revisa la Pestaña 3 para el Resultado Operativo.")

                elif filename.endswith('.pdf'):
                    with st.spinner("Procesando PDF..."):
                        df_update = extract_pdf_data(update_file)
                        if not df_update.empty:
                            conn = get_connection()
                            c = conn.cursor()
                            c.execute("SELECT col_codigo, col_descripcion, col_costo, col_contenido_caja, col_presentacion FROM plantillas_proveedores WHERE nombre_plantilla = ?", (plantilla_pdf,))
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
                                repo = process_mass_update(df_update, marca_manual_pdf, template)
                                st.session_state['global_report'] = repo
                                st.success("✅ PDF Procesado. Revisa la Pestaña 3.")
                        else:
                            st.error("El PDF está vacío tras la purga operativa.")

    # ---------------- TAB 3: REPORTE VISUAL Y EXPORTACIÓN ----------------
    with tab3:
        st.header("Resultado Operativo de la Última Ingesta")

        if 'global_report' in st.session_state and st.session_state['global_report']:
            df_report = pd.DataFrame(st.session_state['global_report'])

            nuevos = len(df_report[df_report['Acción'] == 'NUEVO'])
            actualizados = len(df_report[df_report['Acción'] == 'Actualizado'])

            st.info(f"Resumen: {nuevos} Productos Creados | {actualizados} Productos Actualizados")

            st.dataframe(df_report, use_container_width=True)

            st.write("---")
            st.subheader("Paso Final: Exportar Base Consolidada")
            st.info("Usa este botón para descargar el Inventario Maestro completo, con el formato ideal para importar en el siguiente programa.")

            conn = get_connection()
            df_final = pd.read_sql_query("SELECT sku_interno, codigo_proveedor, descripcion, marca, tipo_venta, capacidad_medida, contenido_caja, costo_actual, fecha_actualizacion FROM productos_maestro", conn)
            conn.close()

            excel_data = to_excel(df_final)
            st.download_button(
                label="📥 Exportar Inventario Maestro Operativo",
                data=excel_data,
                file_name='INVENTARIO_MAESTRO_UNIFICADO_COMPLETO.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )

        else:
            st.info("No hay reporte disponible. Sube y procesa un archivo en la pestaña 2.")

if __name__ == '__main__':
    main()
