import streamlit as st
import sqlite3
import pandas as pd
import requests
import json
import io
import time
from datetime import datetime

DB_NAME = "inventario_barter.db"

@st.cache_resource
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS productos_maestro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_interno TEXT UNIQUE,
            codigo_proveedor TEXT,
            descripcion TEXT,
            marca TEXT,
            costo_neto REAL,
            contenido_caja TEXT,
            fecha_actualizacion TEXT,
            UNIQUE(marca, codigo_proveedor)
        )
    ''')
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_NAME)

def extract_raw_text_from_excel(uploaded_file, batch_size=50):
    text_chunks = []
    try:
        xl = pd.ExcelFile(uploaded_file)
        for sheet in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet, header=None)
            df = df.dropna(how='all')

            # Batch processing: divide the dataframe into smaller chunks
            for start_idx in range(0, len(df), batch_size):
                df_chunk = df.iloc[start_idx:start_idx + batch_size]
                csv_str = df_chunk.to_csv(index=False, header=False)
                text_chunks.append(csv_str)
    except Exception as e:
        st.error(f"Error extrayendo texto del Excel: {e}")
    return text_chunks

def call_gemini_engine(text_data, api_key, batch_num):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}"
    prompt = "Extrae la información comercial de este texto sucio. Ignora basura y metadatos. Devuelve ÚNICAMENTE un JSON con una lista de diccionarios. Claves estrictas: 'codigo_proveedor', 'descripcion', 'costo_neto', 'contenido_caja' (si no existe, pon 1). No incluyas markdown ni explicaciones, solo el JSON puro.\n\nTexto sucio:\n"

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt + text_data}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0
        }
    }

    raw_output = ""
    try:
        response = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload)

        if response.status_code != 200:
            st.warning(f"Error de la API en el Lote {batch_num} (HTTP {response.status_code}). Saltando...")
            return []

        response_json = response.json()

        try:
            raw_output = response_json['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError):
            st.warning(f"La API devolvió una respuesta con formato inesperado en el Lote {batch_num}. Saltando...")
            return []

        raw_output = raw_output.replace('```json', '').replace('```', '').strip()

        data = json.loads(raw_output)
        return data
    except json.JSONDecodeError:
        st.warning(f"Error: La IA no devolvió un JSON válido en el Lote {batch_num} (Truncamiento). Saltando...")
        return []
    except Exception as e:
        st.warning(f"Error llamando a la API de Gemini (REST) en el Lote {batch_num}: {e}. Saltando...")
        return []

def generate_sku(marca, item_id):
    marca_prefix = str(marca)[:3].upper() if len(str(marca)) >= 3 else str(marca).upper().ljust(3, 'X')
    return f"{marca_prefix}-{str(item_id).zfill(5)}"

def process_and_unify(json_data, marca):
    conn = get_connection()
    c = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserts = 0
    updates = 0

    for item in json_data:
        cod_prov = str(item.get('codigo_proveedor', '')).strip()
        desc = str(item.get('descripcion', '')).strip()

        costo_raw = str(item.get('costo_neto', '0')).replace('$', '').strip()
        if '.' in costo_raw and ',' in costo_raw:
            if costo_raw.rfind(',') > costo_raw.rfind('.'):
                costo_raw = costo_raw.replace('.', '').replace(',', '.')
            else:
                costo_raw = costo_raw.replace(',', '')
        elif ',' in costo_raw:
            costo_raw = costo_raw.replace(',', '.')

        try:
            costo = float(costo_raw)
        except ValueError:
            costo = 0.0

        caja = str(item.get('contenido_caja', '1')).strip()

        if not desc or not cod_prov:
            continue

        c.execute("SELECT id FROM productos_maestro WHERE marca = ? AND codigo_proveedor = ?", (marca, cod_prov))
        existing = c.fetchone()

        if existing:
            matched_id = existing[0]
            c.execute('''UPDATE productos_maestro
                         SET descripcion = ?, costo_neto = ?, contenido_caja = ?, fecha_actualizacion = ?
                         WHERE id = ?''', (desc, costo, caja, now, matched_id))
            updates += 1
        else:
            c.execute('''INSERT INTO productos_maestro
                         (codigo_proveedor, descripcion, marca, costo_neto, contenido_caja, fecha_actualizacion)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                         (cod_prov, desc, marca, costo, caja, now))
            new_id = c.lastrowid
            sku = generate_sku(marca, new_id)
            c.execute("UPDATE productos_maestro SET sku_interno = ? WHERE id = ?", (sku, new_id))
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
    st.set_page_config(page_title="Embudo IA (Barter Plus)", layout="wide")
    init_db()

    with st.sidebar:
        st.header("Configuración de Motor IA")
        api_key = st.text_input("Gemini API Key", type="password")
        if not api_key:
            st.warning("⚠️ Ingresa tu API Key para activar el motor de extracción.")

    st.title("Sistema de Extracción IA y Unificación (Barter Plus)")

    st.subheader("1. Embudo de Extracción Masiva")

    uploaded_files = st.file_uploader("Sube Listas de Proveedores (Excel)", type=["xlsx", "xls"], accept_multiple_files=True)

    if uploaded_files:
        st.write("### Asignación de Marca")
        file_marcas = {}
        for file in uploaded_files:
            file_marcas[file.name] = st.text_input(f"Ingresa la Marca para el archivo: {file.name}", key=f"marca_{file.name}").strip().upper()

        if st.button("Ejecutar Motor IA y Unificar"):
            if not api_key:
                st.error("No se puede procesar sin una API Key válida.")
                st.stop()

            all_inserts = 0
            all_updates = 0

            progress_bar = st.progress(0)

            for i, file in enumerate(uploaded_files):
                marca = file_marcas[file.name]
                if not marca:
                    st.warning(f"Saltando {file.name}: No se especificó la marca.")
                    continue

                with st.spinner(f"[{file.name}] Dividiendo en lotes operativos (Batching)..."):
                    text_chunks = extract_raw_text_from_excel(file, batch_size=50)

                master_json_list = []
                total_chunks = len(text_chunks)

                for idx, chunk in enumerate(text_chunks):
                    with st.spinner(f"[{file.name}] Procesando Lote {idx + 1} de {total_chunks} mediante IA..."):
                        json_data = call_gemini_engine(chunk, api_key, batch_num=(idx + 1))

                        if json_data:
                            master_json_list.extend(json_data)

                        # Update progress bar fractionally per batch across all files
                        total_files = len(uploaded_files)
                        base_progress = i / total_files
                        chunk_progress = ((idx + 1) / total_chunks) / total_files
                        progress_bar.progress(base_progress + chunk_progress)

                        # Pequeña pausa para no saturar los rate limits de la API
                        time.sleep(2)

                # Upsert consolidated data for this file
                if master_json_list:
                    with st.spinner(f"[{file.name}] Unificando e insertando resultados en la Base Maestra..."):
                        ins, upd = process_and_unify(master_json_list, marca)
                        all_inserts += ins
                        all_updates += upd

            st.success(f"✅ ¡Proceso de Embudo IA finalizado! Productos Nuevos (Creados): {all_inserts} | Productos Actualizados: {all_updates}")

    st.write("---")
    st.subheader("2. Inventario Maestro (Exportación Final)")

    conn = get_connection()
    df_maestro = pd.read_sql_query("SELECT sku_interno, codigo_proveedor, descripcion, marca, costo_neto, contenido_caja, fecha_actualizacion FROM productos_maestro", conn)
    conn.close()

    st.dataframe(df_maestro, use_container_width=True, hide_index=True)

    if not df_maestro.empty:
        st.success("La Base de Datos Maestra está lista para ser transferida al siguiente sistema.")
        excel_data = to_excel(df_maestro)
        st.download_button(
            label="📥 Descargar Inventario_Maestro_Unificado.xlsx",
            data=excel_data,
            file_name='Inventario_Maestro_Unificado.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

if __name__ == '__main__':
    main()
