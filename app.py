import streamlit as st
import sqlite3
import pandas as pd
import pdfplumber
import re
from datetime import datetime
from thefuzz import fuzz
import io

DB_NAME = "master_data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Crear tablas si no existen
    c.execute('''
        CREATE TABLE IF NOT EXISTS productos_maestro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_interno TEXT UNIQUE,
            codigo_proveedor TEXT,
            descripcion TEXT,
            marca TEXT,
            tipo_venta TEXT,
            capacidad_medida TEXT,
            costo_actual REAL,
            fecha_actualizacion TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS plantillas_proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proveedor_marca TEXT UNIQUE,
            col_codigo TEXT,
            col_descripcion TEXT,
            col_precio TEXT
        )
    ''')

    # Resiliencia Operativa: Auto-corregir esquema si faltan columnas
    c.execute("PRAGMA table_info(productos_maestro)")
    columns = [info[1] for info in c.fetchall()]

    required_columns = {
        'codigo_interno': 'TEXT UNIQUE',
        'tipo_venta': 'TEXT',
        'capacidad_medida': 'TEXT'
    }

    for col, dtype in required_columns.items():
        if col not in columns:
            try:
                c.execute(f"ALTER TABLE productos_maestro ADD COLUMN {col} {dtype}")
                st.toast(f"🛠️ Autocorrección de BD: Columna '{col}' agregada.", icon="🔧")
            except sqlite3.OperationalError as e:
                # Sometimes adding UNIQUE constraint directly in ALTER TABLE is not supported in older SQLite versions,
                # but standard TEXT is usually fine. Let's fallback to TEXT if it fails.
                if 'UNIQUE' in dtype:
                   c.execute(f"ALTER TABLE productos_maestro ADD COLUMN {col} TEXT")
                else:
                    raise e

    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_NAME)

def purge_dataframe(df):
    """
    Módulo de Purga Operativa.
    Limpia el DataFrame aplicando reglas estrictas.
    """
    if df.empty:
        return df

    # 1. Limpieza Vertical Total: Eliminar filas 100% vacías (NaN o strings vacíos)
    df = df.replace(r'^\s*$', pd.NA, regex=True)
    df = df.dropna(how='all')

    if df.empty:
        return df

    rows_to_keep = []

    # Regex Patterns
    # Palabras clave comunes de encabezados
    header_pattern = re.compile(r'\b(CÓDIGO|CODIGO|DESCRIPCIÓN|DESCRIPCION|NETO|PRECIO LISTA|PRECIO|PRODUCTO|FILTROS|ACEITES|ARTICULO|ARTÍCULO|MARCA)\b', re.IGNORECASE)

    # Frases de aviso/disclaimers
    disclaimer_pattern = re.compile(r'(LISTA SUJETA A CAMBIOS|NO INCLUYE IVA|VÁLIDA HASTA|VALIDA HASTA|CONFIRMAR PRECIOS|PAGINA \d+|PÁGINA \d+|SOLO CONTADO|LOS PRECIOS)', re.IGNORECASE)

    for index, row in df.iterrows():
        row_str = " ".join([str(val) for val in row if pd.notna(val)])

        # Filtro de Disclaimers/Incertidumbre
        if disclaimer_pattern.search(row_str):
            continue

        # Filtro de Encabezados/Títulos Operativos
        header_matches = 0
        valid_cells = 0
        for val in row:
            if pd.notna(val) and str(val).strip():
                valid_cells += 1
                if header_pattern.search(str(val)):
                    header_matches += 1

        # Si más del 50% de las celdas válidas contienen palabras de encabezado, descartar
        if valid_cells > 0 and (header_matches / valid_cells) > 0.5:
            continue

        # Si pasó todos los filtros, conservar la fila
        rows_to_keep.append(index)

    purged_df = df.loc[rows_to_keep].reset_index(drop=True)
    return purged_df

def detect_unit_and_capacity(description):
    """
    Lógica de SKU Propio y Detección de Medida (Regex)
    """
    desc_upper = str(description).upper()

    tipo_venta = "UNIDAD"
    capacidad_medida = "Unidad"

    # Regex para granel
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
        # Regex para unidad
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
    marca_prefix = marca[:3].upper() if len(marca) >= 3 else marca.upper().ljust(3, 'X')
    tipo_code = "UN" if tipo_venta == "UNIDAD" else "GR"
    return f"{marca_prefix}-{tipo_code}-{str(item_id).zfill(5)}"

def parse_file(uploaded_file):
    filename = uploaded_file.name.lower()
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(uploaded_file, header=None)
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(uploaded_file, header=None)
        elif filename.endswith('.pdf'):
            data = []
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        data.extend(table)
            if data:
                df = pd.DataFrame(data)
            else:
                st.error("No se encontraron tablas estructuradas en el PDF.")
                return pd.DataFrame()
        else:
            st.error("Formato de archivo no soportado.")
            return pd.DataFrame()

        # Aplicar limpieza y asegurar nombres genéricos para columnas
        df = purge_dataframe(df)
        df.columns = [f"Col_{i}" for i in range(len(df.columns))]
        return df
    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
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

def process_mass_update(df, marca, template):
    col_codigo = template['col_codigo']
    col_desc = template['col_descripcion']
    col_precio = template['col_precio']

    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT id, codigo_proveedor, descripcion, tipo_venta FROM productos_maestro WHERE marca = ?", (marca,))
    db_items = c.fetchall()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updates = 0
    inserts = 0

    for _, row in df.iterrows():
        cod_prov = str(row[col_codigo]).strip() if col_codigo in df.columns and pd.notna(row[col_codigo]) else ""
        desc = str(row[col_desc]).strip() if col_desc in df.columns and pd.notna(row[col_desc]) else ""
        costo = clean_currency(row[col_precio]) if col_precio in df.columns else 0.0

        if not desc or desc.lower() in ['nan', 'none', '']:
            continue

        tipo_venta, capacidad = detect_unit_and_capacity(desc)
        matched_id = None

        # 1. Match Exacto por Código Proveedor
        if cod_prov and cod_prov.lower() not in ['nan', 'none']:
            for item in db_items:
                if item[1] == cod_prov and item[3] == tipo_venta:
                    matched_id = item[0]
                    break

        # 2. Match Fuzzy Inteligente (Filtro estricto por Marca y Tipo de Venta)
        if not matched_id:
            best_score = 0
            best_id = None
            for item in db_items:
                # El filtro de marca ya se hizo en el SELECT, filtramos estricto por tipo_venta
                if item[3] == tipo_venta:
                    score = fuzz.token_sort_ratio(desc.lower(), item[2].lower())
                    if score > best_score:
                        best_score = score
                        best_id = item[0]

            # Umbral de similitud del 85%
            if best_score >= 85:
                matched_id = best_id

        if matched_id:
            c.execute("UPDATE productos_maestro SET costo_actual = ?, fecha_actualizacion = ? WHERE id = ?", (costo, now, matched_id))
            updates += 1
        else:
            c.execute('''INSERT INTO productos_maestro
                         (codigo_proveedor, descripcion, marca, tipo_venta, capacidad_medida, costo_actual, fecha_actualizacion)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                         (cod_prov, desc, marca, tipo_venta, capacidad, costo, now))
            new_id = c.lastrowid
            sku = generate_sku(marca, tipo_venta, new_id)
            c.execute("UPDATE productos_maestro SET codigo_interno = ? WHERE id = ?", (sku, new_id))

            # Actualizar memoria para evitar duplicados en la misma subida
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
    st.set_page_config(page_title="Arquitectura de Mapeo y Purga", layout="wide")
    st.title("Gestor Resiliente de Listas de Proveedores")

    init_db()

    tab1, tab2, tab3 = st.tabs(["1. Entrenamiento de Plantillas", "2. Actualización Masiva", "3. Inventario Maestro"])

    # ---------------- TAB 1: ENTRENAMIENTO ----------------
    with tab1:
        st.header("Entrenamiento de Plantillas de Proveedores")
        st.info("Sube una lista sucia de ejemplo de un proveedor para enseñarle al sistema cómo leerla. El sistema la purgará automáticamente.")

        train_file = st.file_uploader("Sube lista de ejemplo (Excel/PDF)", type=["xlsx", "xls", "pdf"], key="train_file")
        marca_train = st.text_input("Nombre de la Marca/Proveedor (Ej: Shell)", key="train_marca").strip().upper()

        if train_file and marca_train:
            df_train = parse_file(train_file)

            if not df_train.empty:
                st.success("✅ Archivo leído y purgado exitosamente.")
                st.write("### Vista previa de los datos limpios:")
                st.dataframe(df_train.head(10))

                cols_available = list(df_train.columns)

                st.write("### Mapeo de Columnas")
                col1, col2, col3 = st.columns(3)
                with col1:
                    sel_cod = st.selectbox("Columna Código Proveedor", cols_available)
                with col2:
                    sel_desc = st.selectbox("Columna Descripción", cols_available)
                with col3:
                    sel_prec = st.selectbox("Columna Precio/Costo", cols_available)

                if st.button("Guardar Plantilla"):
                    if len(set([sel_cod, sel_desc, sel_prec])) < 3:
                         st.warning("⚠️ Selecciona una columna distinta para cada campo.")
                    else:
                        conn = get_connection()
                        c = conn.cursor()
                        try:
                            c.execute('''INSERT INTO plantillas_proveedores (proveedor_marca, col_codigo, col_descripcion, col_precio)
                                         VALUES (?, ?, ?, ?)
                                         ON CONFLICT(proveedor_marca) DO UPDATE SET
                                         col_codigo=excluded.col_codigo, col_descripcion=excluded.col_descripcion, col_precio=excluded.col_precio''',
                                      (marca_train, sel_cod, sel_desc, sel_prec))
                            conn.commit()
                            st.success(f"Plantilla para {marca_train} guardada exitosamente.")
                        except Exception as e:
                            st.error(f"Error guardando plantilla: {e}")
                        finally:
                            conn.close()
            else:
                st.error("No se pudieron extraer datos (o todos fueron purgados).")

    # ---------------- TAB 2: ACTUALIZACIÓN MASIVA ----------------
    with tab2:
        st.header("Actualización Masiva de Listas")
        st.info("Sube la nueva lista de precios de un proveedor ya entrenado. El sistema purgará, unificará y actualizará automáticamente usando el mapeo guardado.")

        conn = get_connection()
        df_templates = pd.read_sql_query("SELECT proveedor_marca FROM plantillas_proveedores", conn)
        conn.close()

        if df_templates.empty:
            st.warning("No hay plantillas guardadas. Entrena una plantilla primero en la pestaña 1.")
        else:
            marcas_guardadas = df_templates['proveedor_marca'].tolist()
            marca_update = st.selectbox("Selecciona la Marca/Proveedor", ["-- Seleccionar --"] + marcas_guardadas)

            update_file = st.file_uploader("Sube nueva lista de precios (Excel/PDF)", type=["xlsx", "xls", "pdf"], key="update_file")

            if st.button("Procesar Lista"):
                if update_file and marca_update != "-- Seleccionar --":
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("SELECT col_codigo, col_descripcion, col_precio FROM plantillas_proveedores WHERE proveedor_marca = ?", (marca_update,))
                    template_row = c.fetchone()
                    conn.close()

                    if template_row:
                        template = {
                            'col_codigo': template_row[0],
                            'col_descripcion': template_row[1],
                            'col_precio': template_row[2]
                        }

                        with st.spinner("Purgando archivo..."):
                            df_update = parse_file(update_file)

                        if not df_update.empty:
                            with st.spinner("Realizando matching y actualizando Maestro..."):
                                ins, upd = process_mass_update(df_update, marca_update, template)
                                st.success(f"✅ Proceso completado para {marca_update}. Insertados: {ins} | Actualizados: {upd}")
                        else:
                            st.error("Archivo vacío tras la purga.")
                else:
                    st.error("Selecciona una marca y sube un archivo.")

    # ---------------- TAB 3: INVENTARIO MAESTRO ----------------
    with tab3:
        st.header("Inventario Maestro Unificado")

        conn = get_connection()
        df_maestro = pd.read_sql_query("SELECT * FROM productos_maestro", conn)
        conn.close()

        st.dataframe(df_maestro, use_container_width=True)

        if not df_maestro.empty:
            excel_data = to_excel(df_maestro)
            st.download_button(
                label="📥 Exportar Inventario a Excel",
                data=excel_data,
                file_name='inventario_maestro_unificado.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
        else:
            st.info("El inventario maestro está vacío.")

if __name__ == '__main__':
    main()
