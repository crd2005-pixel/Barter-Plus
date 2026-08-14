import streamlit as st
import pandas as pd
import sqlite3
import re
import io
import json
import uuid
import datetime
from thefuzz import fuzz

st.set_page_config(page_title="Barter Plus v6.0", layout="wide", initial_sidebar_state="expanded")

@st.cache_resource
def init_db():
    conn = sqlite3.connect("inventario_barter.db", check_same_thread=False)
    c = conn.cursor()
    # Tabla maestro
    c.execute('''
        CREATE TABLE IF NOT EXISTS productos_maestro (
            sku TEXT PRIMARY KEY,
            codigo_proveedor TEXT,
            descripcion TEXT,
            marca TEXT,
            precio_costo REAL,
            fecha_actualizacion TEXT,
            metadata_extra TEXT
        )
    ''')

    # Auto-correccion de schema (resiliencia)
    try:
        c.execute("ALTER TABLE productos_maestro ADD COLUMN marca TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE productos_maestro ADD COLUMN precio_costo REAL")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE productos_maestro ADD COLUMN fecha_actualizacion TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE productos_maestro ADD COLUMN metadata_extra TEXT")
    except sqlite3.OperationalError:
        pass

    # Tabla plantillas
    c.execute('''
        CREATE TABLE IF NOT EXISTS plantillas (
            id TEXT PRIMARY KEY,
            nombre TEXT,
            configuracion TEXT
        )
    ''')
    conn.commit()
    return conn

conn = init_db()

def clean_currency(value):
    if pd.isna(value):
        return 0.0
    val_str = str(value).strip()

    # Check if the string matches the general pattern of currency digits/symbols
    if re.search(r'[\d\.,]', val_str):
        # Remove anything that is not a digit, comma, or dot (like $ or spaces)
        val_str = re.sub(r'[^\d\.,]', '', val_str)

        # Count dots and commas
        dots = val_str.count('.')
        commas = val_str.count(',')

        # If it matches XX.XXX,XX (Latin format)
        if dots > 0 and commas == 1 and val_str.rfind(',') > val_str.rfind('.'):
            val_str = val_str.replace('.', '').replace(',', '.')
        # If it matches XX,XXX.XX (US format)
        elif commas > 0 and dots == 1 and val_str.rfind('.') > val_str.rfind(','):
            val_str = val_str.replace(',', '')
        # If it only has comma, treat as decimal if single
        elif commas == 1 and dots == 0:
            val_str = val_str.replace(',', '.')
        elif commas > 1 and dots == 0:
            val_str = val_str.replace(',', '')
        # If it has dots but NO commas, it might be 1.500 (one thousand five hundred)
        # or 1.50 (one point five). In Argentina format usually dot is thousands separator.
        elif dots >= 1 and commas == 0:
            # If the last dot has exactly 3 digits after it, assume it's a thousands separator
            # Only if it's not a clear decimal like 1.50 (2 digits) or 1.5 (1 digit)
            parts = val_str.split('.')
            if len(parts[-1]) == 3:
                val_str = val_str.replace('.', '')

    val_str = re.sub(r'[^\d.]', '', val_str)
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def generate_sku(marca, autoincrement_id):
    marca_clean = re.sub(r'[^a-zA-Z0-9]', '', str(marca).upper())[:3]
    if not marca_clean:
        marca_clean = "XXX"
    return f"{marca_clean}-UN-{str(autoincrement_id).zfill(5)}"

def smart_alias_columns(df):
    # This acts as an initial normalizer before strict mapping
    new_cols = []
    for col in df.columns:
        col_str = str(col).lower()
        if 'cod' in col_str or 'cód' in col_str:
            new_cols.append('CÓDIGO')
        elif 'desc' in col_str or 'art' in col_str:
            new_cols.append('DESCRIPCIÓN')
        elif 'precio' in col_str or 'costo' in col_str or '$' in col_str:
            new_cols.append('PRECIO')
        else:
            new_cols.append(col)

    # Ensure unique column names for pyarrow safety
    unique_cols = []
    seen = {}
    for c in new_cols:
        if c not in seen:
            seen[c] = 1
            unique_cols.append(c)
        else:
            unique_cols.append(f"{c}_{seen[c]}")
            seen[c] += 1

    df.columns = unique_cols
    return df

def apply_purger(df):
    # Discard rows that are likely metadata/disclaimers
    # E.g. empty rows or rows where the majority of columns are NaN
    threshold = len(df.columns) * 0.3 # At least 30% of columns must have data
    df = df.dropna(thresh=int(threshold))

    # Simple regex based row purger for common useless text
    mask = df.astype(str).apply(lambda x: x.str.contains(r'lista de precios|vigente desde|hoja|pág|tel:|dirección|iva', flags=re.IGNORECASE)).any(axis=1)
    return df[~mask].reset_index(drop=True)

def destack_dataframe(df, is_stacked=False):
    if not is_stacked:
        return [df]

    tables = []
    current_table = []

    for idx, row in df.iterrows():
        # Detect a "header" row by checking if it has many non-null string values
        # and checking fuzz ratio with previous rows. A naive implementation:
        non_nulls = row.notna().sum()
        if non_nulls > 2 and row.astype(str).str.contains(r'[a-zA-Z]').sum() > 2:
            if current_table and len(current_table) > 2:
                # Potential new table start
                # Use fuzz to see if this row resembles the first row of current_table (the assumed header)
                header = current_table[0]
                # Compare string representations
                sim = fuzz.token_set_ratio(" ".join(header.astype(str)), " ".join(row.astype(str)))

                # If they are very different, it might be a new table structure
                if sim < 85:
                    temp_df = pd.DataFrame(current_table[1:], columns=current_table[0])
                    tables.append(temp_df)
                    current_table = [row]
                    continue

        current_table.append(row)

    if current_table and len(current_table) > 1:
        temp_df = pd.DataFrame(current_table[1:], columns=current_table[0])
        tables.append(temp_df)
    elif current_table and len(tables) == 0:
        # Just the original
        tables.append(df)

    return tables

# ================= UI AND WIZARD LOGIC =================

st.sidebar.title("Barter Plus v6.0")
st.sidebar.markdown("---")
modo = st.sidebar.radio("¿Qué deseas hacer?", ["Entrenar Sistema (Wizard)", "Normalizar (Ingesta Masiva)", "Inventario Maestro Unificado"])

if modo == "Entrenar Sistema (Wizard)":
    st.header("Wizard de Entrenamiento 🧙‍♂️")
    st.write("Sube un archivo de ejemplo para enseñar al sistema cómo leer la lista de este proveedor.")

    uploaded_file = st.file_uploader("Sube un Excel o PDF de ejemplo", type=["xlsx", "xls", "pdf"])

    if uploaded_file:
        try:
            # Handle reading files (simplistic for this example, focusing on Excel)
            if uploaded_file.name.endswith(('xlsx', 'xls')):
                xl = pd.ExcelFile(uploaded_file)
                sheet_names = xl.sheet_names
                selected_sheet = st.selectbox("Selecciona la Pestaña a procesar", sheet_names)

                df_preview = pd.read_excel(xl, sheet_name=selected_sheet, nrows=50)

                # Enforce unique generic column names (Col_0, Col_1, etc.) for mapping
                df_preview.columns = [f"Col_{i}" for i in range(len(df_preview.columns))]
                st.dataframe(df_preview.head())

                st.subheader("Mapeo de Columnas Críticas")
                # Prepend None option
                col_options = ["[Ninguno (No Existe)]"] + list(df_preview.columns)

                col_codigo = st.selectbox("Define Columna de CÓDIGO", col_options)
                col_desc = st.selectbox("Define Columna de DESCRIPCIÓN", col_options)
                col_precio = st.selectbox("Define Columna de PRECIO", col_options)
                col_marca = st.selectbox("Define Columna de MARCA (Opcional)", col_options)

                st.subheader("Inteligencia de Mapeo Guiado Complejo")
                manejar_multiple = st.checkbox("¿Manejar Una Fila = Múltiples Códigos, Medidas, Precios?")
                manejar_apiladas = st.checkbox("¿Manejar Tablas Apiladas Verticalmente (una sobre otra)?")

                nombre_plantilla = st.text_input("Nombre de la Plantilla", placeholder="Ej: Lista_Proveedor_A")

                if st.button("Guardar Plantilla"):
                    if not nombre_plantilla:
                        st.error("Por favor, ingresa un nombre para la plantilla.")
                    else:
                        config = {
                            "col_codigo": col_codigo,
                            "col_desc": col_desc,
                            "col_precio": col_precio,
                            "col_marca": col_marca,
                            "manejar_multiple": manejar_multiple,
                            "manejar_apiladas": manejar_apiladas,
                            "sheet_name": selected_sheet
                        }

                        c = conn.cursor()
                        # Use replace/insert to update if exists
                        c.execute("INSERT OR REPLACE INTO plantillas (id, nombre, configuracion) VALUES (?, ?, ?)",
                                  (str(uuid.uuid4()), nombre_plantilla, json.dumps(config)))
                        conn.commit()
                        st.success(f"Plantilla '{nombre_plantilla}' guardada con éxito.")

            elif uploaded_file.name.endswith('pdf'):
                st.warning("El procesamiento de PDF en el Wizard está limitado en este demo. Por favor use Excel para testear todas las funciones.")
        except Exception as e:
            st.error(f"Error procesando el archivo: {e}")

elif modo == "Normalizar (Ingesta Masiva)":
    st.header("Motor de Ingesta Masiva 🚀")

    # Load templates
    c = conn.cursor()
    c.execute("SELECT id, nombre, configuracion FROM plantillas")
    plantillas_db = c.fetchall()

    if not plantillas_db:
        st.warning("No hay plantillas guardadas. Ve al Wizard para crear una.")
    else:
        plantilla_dict = {p[1]: json.loads(p[2]) for p in plantillas_db}
        selected_template_name = st.selectbox("Selecciona una Plantilla de Mapeo", list(plantilla_dict.keys()))
        config = plantilla_dict[selected_template_name]

        st.info(f"Usando plantilla configurada para hojas: '{config.get('sheet_name', 'N/A')}'")

        uploaded_files = st.file_uploader("Sube archivos caóticos (Excel)", type=["xlsx", "xls"], accept_multiple_files=True)

        if uploaded_files and st.button("Procesar Archivos"):
            creados = 0
            actualizados = 0
            with st.spinner("Procesando..."):
                for uf in uploaded_files:
                    try:
                        xl = pd.ExcelFile(uf)
                        sheet = config.get('sheet_name')
                        if sheet not in xl.sheet_names:
                            st.warning(f"La pestaña '{sheet}' no existe en {uf.name}. Procesando primera pestaña por defecto.")
                            sheet = xl.sheet_names[0]

                        df = pd.read_excel(xl, sheet_name=sheet)

                        # Apply smart alias (first pass)
                        df = smart_alias_columns(df)

                        # Apply Purger
                        df = apply_purger(df)

                        # Destacker
                        tablas = destack_dataframe(df, is_stacked=config.get('manejar_apiladas', False))

                        for tabla in tablas:
                            # Force columns to Col_0, Col_1 to apply template
                            tabla.columns = [f"Col_{i}" for i in range(len(tabla.columns))]

                            for idx, row in tabla.iterrows():
                                # Extract based on template mapping
                                cod_col = config.get('col_codigo')
                                desc_col = config.get('col_desc')
                                precio_col = config.get('col_precio')
                                marca_col = config.get('col_marca')

                                codigo = str(row[cod_col]) if cod_col != "[Ninguno (No Existe)]" and cod_col in tabla.columns else ""
                                desc = str(row[desc_col]) if desc_col != "[Ninguno (No Existe)]" and desc_col in tabla.columns else ""
                                precio_raw = row[precio_col] if precio_col != "[Ninguno (No Existe)]" and precio_col in tabla.columns else 0.0
                                marca = str(row[marca_col]) if marca_col != "[Ninguno (No Existe)]" and marca_col in tabla.columns else selected_template_name

                                precio = clean_currency(precio_raw)

                                if not desc or pd.isna(desc) or desc == 'nan':
                                    continue

                                # Auto-generate SKU if no valid code
                                if not codigo or codigo == 'nan':
                                    # Very basic auto-id for this demo, normally you query max id from DB
                                    c.execute("SELECT COUNT(*) FROM productos_maestro")
                                    count = c.fetchone()[0]
                                    sku = generate_sku(marca, count + 1 + creados)
                                else:
                                    sku = generate_sku(marca, codigo)

                                # Check DB
                                c.execute("SELECT sku FROM productos_maestro WHERE sku = ?", (sku,))
                                exists = c.fetchone()

                                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                                if exists:
                                    c.execute("""
                                        UPDATE productos_maestro
                                        SET precio_costo = ?, descripcion = ?, fecha_actualizacion = ?
                                        WHERE sku = ?
                                    """, (precio, desc, now, sku))
                                    actualizados += 1
                                else:
                                    c.execute("""
                                        INSERT INTO productos_maestro (sku, codigo_proveedor, descripcion, marca, precio_costo, fecha_actualizacion)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    """, (sku, codigo, desc, marca, precio, now))
                                    creados += 1

                        conn.commit()

                    except Exception as e:
                        st.error(f"Error procesando {uf.name}: {e}")

            st.success("Procesamiento completado.")

            st.subheader("Reporte Operativo")
            col1, col2 = st.columns(2)
            col1.metric("Productos Creados", creados)
            col2.metric("Productos Actualizados", actualizados)

elif modo == "Inventario Maestro Unificado":
    st.header("Inventario Maestro Unificado 📦")

    df_maestro = pd.read_sql_query("SELECT * FROM productos_maestro", conn)

    if df_maestro.empty:
        st.info("El inventario está vacío.")
    else:
        st.dataframe(df_maestro, use_container_width=True)

        # Export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_maestro.to_excel(writer, index=False, sheet_name='Inventario')

        st.download_button(
            label="Descargar Inventario Maestro a Excel",
            data=output.getvalue(),
            file_name="Inventario_Maestro.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
