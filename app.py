import streamlit as st
import sqlite3
import pandas as pd
import pdfplumber
import re
from datetime import datetime
from thefuzz import fuzz
import io
import os

DB_NAME = "master_data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
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
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_NAME)

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

def detect_unit_and_capacity(description):
    desc_upper = str(description).upper()

    # Defaults
    tipo_venta = "UNIDAD"
    capacidad_medida = "Unidad"

    # Granel patterns
    match_granel = re.search(r'\b(TAMBOR|TBR|200\s*L|GRANEL|BALDE|20\s*L)\b', desc_upper)

    if match_granel:
        tipo_venta = "GRANEL"
        cap = match_granel.group(1)
        # Normalize
        if "200" in cap:
            capacidad_medida = "200L"
        elif "20" in cap:
            capacidad_medida = "20L"
        elif cap in ["TAMBOR", "TBR"]:
            capacidad_medida = "Tambor"
        elif cap == "BALDE":
            capacidad_medida = "Balde"
        else:
            capacidad_medida = "Granel"
    else:
        tipo_venta = "UNIDAD"
        # Unidad patterns
        match_unidad = re.search(r'\b(1\s*L|4\s*L|BOTELLA|UNIDAD|FILTRO)\b', desc_upper)
        if match_unidad:
            cap = match_unidad.group(1)
            if "1" in cap and "L" in cap:
                capacidad_medida = "1L"
            elif "4" in cap and "L" in cap:
                capacidad_medida = "4L"
            elif cap == "BOTELLA":
                capacidad_medida = "Botella"
            elif cap == "FILTRO":
                capacidad_medida = "Filtro"
            else:
                capacidad_medida = "Unidad"
        else:
            capacidad_medida = "Unidad"

    return tipo_venta, capacidad_medida

def generate_sku(marca, tipo_venta, item_id):
    marca_prefix = marca[:3].upper() if len(marca) >= 3 else marca.upper().ljust(3, 'X')
    tipo_code = "UN" if tipo_venta == "UNIDAD" else "GR"
    return f"{marca_prefix}-{tipo_code}-{str(item_id).zfill(4)}"

def parse_file(uploaded_file):
    filename = uploaded_file.name.lower()
    try:
        if filename.endswith('.csv'):
            return pd.read_csv(uploaded_file)
        elif filename.endswith(('.xls', '.xlsx')):
            return pd.read_excel(uploaded_file)
        elif filename.endswith('.pdf'):
            data = []
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        data.extend(table)
            if data and len(data) > 1:
                header = data[0]
                df = pd.DataFrame(data[1:], columns=header)
                return df
            else:
                st.error("No se encontraron tablas estructuradas en el PDF.")
                return pd.DataFrame()
        else:
            st.error("Formato de archivo no soportado.")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
        return pd.DataFrame()

def process_data(df, marca):
    if df.empty:
        return

    # Attempt to standardise columns
    cols = [str(c).lower() for c in df.columns]

    cod_col = None
    desc_col = None
    costo_col = None

    for c in df.columns:
        cl = str(c).lower()
        if not cod_col and ('cod' in cl or 'código' in cl):
            cod_col = c
        elif not desc_col and ('desc' in cl or 'producto' in cl or 'articulo' in cl or 'artículo' in cl):
            desc_col = c
        elif not costo_col and ('cost' in cl or 'precio' in cl or 'valor' in cl):
            costo_col = c

    if not desc_col or not costo_col:
        st.error(f"No se pudieron identificar las columnas 'Descripción' y 'Costo'. Columnas detectadas: {list(df.columns)}")
        return

    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT id, codigo_proveedor, descripcion, tipo_venta FROM productos_maestro WHERE marca = ?", (marca,))
    db_items = c.fetchall()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    updates = 0
    inserts = 0

    for _, row in df.iterrows():
        cod_prov = str(row[cod_col]).strip() if cod_col and pd.notna(row[cod_col]) else ""
        desc = str(row[desc_col]).strip() if pd.notna(row[desc_col]) else ""
        costo = clean_currency(row[costo_col])

        if not desc or desc.lower() in ['nan', 'none', '']:
            continue

        tipo_venta, capacidad = detect_unit_and_capacity(desc)

        matched_id = None

        # Match exacto por código de proveedor
        if cod_prov and cod_prov.lower() not in ['nan', 'none', '']:
            for item in db_items:
                if item[1] == cod_prov and item[3] == tipo_venta:
                    matched_id = item[0]
                    break

        # Match aproximado por descripción si no hay código o no se encontró
        if not matched_id:
            best_score = 0
            best_id = None
            for item in db_items:
                if item[3] == tipo_venta: # Must match tipo_venta
                    score = fuzz.token_sort_ratio(desc.lower(), item[2].lower())
                    if score > best_score:
                        best_score = score
                        best_id = item[0]
            if best_score >= 85:
                matched_id = best_id

        if matched_id:
            c.execute("UPDATE productos_maestro SET costo_actual = ?, fecha_actualizacion = ? WHERE id = ?", (costo, now, matched_id))
            updates += 1
        else:
            c.execute('''INSERT INTO productos_maestro (codigo_proveedor, descripcion, marca, tipo_venta, capacidad_medida, costo_actual, fecha_actualizacion)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''', (cod_prov, desc, marca, tipo_venta, capacidad, costo, now))
            new_id = c.lastrowid
            sku = generate_sku(marca, tipo_venta, new_id)
            c.execute("UPDATE productos_maestro SET codigo_interno = ? WHERE id = ?", (sku, new_id))

            db_items.append((new_id, cod_prov, desc, tipo_venta))
            inserts += 1

    conn.commit()
    conn.close()

    st.success(f"✅ Procesamiento completado. Productos insertados: {inserts} | Productos actualizados: {updates}")

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario Maestro')
    return output.getvalue()

def main():
    st.set_page_config(page_title="Gestor de Inventario Maestro", layout="wide")
    st.title("Gestor de Inventario Maestro y Precios")

    init_db()

    st.sidebar.header("Subir Archivo de Proveedor")
    uploaded_file = st.sidebar.file_uploader("Selecciona archivo (Excel o PDF)", type=["xlsx", "xls", "pdf"])
    marca_input = st.sidebar.text_input("Marca / Proveedor (Ej: Shell)")

    if st.sidebar.button("Procesar Archivo"):
        if uploaded_file and marca_input:
            df = parse_file(uploaded_file)
            if not df.empty:
                st.write("### Vista previa de los datos extraídos:")
                st.dataframe(df.head())
                with st.spinner("Procesando datos y unificando inventario..."):
                    process_data(df, marca_input.strip())
        else:
            st.sidebar.error("Por favor sube un archivo y especifica la Marca/Proveedor.")

    st.header("Inventario Maestro")

    conn = get_connection()
    df_maestro = pd.read_sql_query("SELECT * FROM productos_maestro", conn)
    conn.close()

    st.dataframe(df_maestro)

    if not df_maestro.empty:
        excel_data = to_excel(df_maestro)
        st.download_button(
            label="📥 Exportar Inventario a Excel",
            data=excel_data,
            file_name='inventario_maestro.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

if __name__ == '__main__':
    main()
