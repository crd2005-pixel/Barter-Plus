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
    """
    Inicializa la base de datos agrupadora.
    """
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

def extract_raw_text_from_excel(uploaded_file):
    """
    Lee todas las pestañas y las convierte a texto crudo (CSV).
    """
    text_chunks = []
    try:
        xl = pd.ExcelFile(uploaded_file)
        for sheet in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet, header=None)
            df = df.dropna(how='all')
            # Limit rows per chunk to avoid massive payloads if needed,
            # but Gemini 1.5 has 1M context window, so we just convert the sheet to CSV string.
            csv_str = df.to_csv(index=False, header=False)
            text_chunks.append(csv_str)
    except Exception as e:
        st.error(f"Error extrayendo texto del Excel: {e}")
    return text_chunks

def call_gemini_engine(text_data, api_key):
    """
    Motor IA: Llama a Gemini para limpiar el texto y devolver JSON estructurado usando REST API pura
    apuntando al modelo gemini-1.5-flash estable.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
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

    try:
        response = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload)

        if response.status_code != 200:
            st.error(f"Error de la API (HTTP {response.status_code}):")
            st.code(response.text)
            return []

        response_json = response.json()

        # Extract the text content from the API response
        try:
            raw_output = response_json['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError):
            st.error("La API devolvió una respuesta con formato inesperado.")
            st.code(response.text)
            return []

        # Remove markdown formatting if present
        raw_output = raw_output.replace('```json', '').replace('```', '').strip()

        data = json.loads(raw_output)
        return data
    except json.JSONDecodeError:
        st.error("Error: La IA no devolvió un JSON válido.")
        st.code(raw_output)
        return []
    except Exception as e:
        st.error(f"Error llamando a la API de Gemini (REST): {e}")
        return []

def generate_sku(marca, item_id):
    """
    Generador de SKU Único: [MARCA]-[ID_AUTONUMERICO]
    """
    marca_prefix = str(marca)[:3].upper() if len(str(marca)) >= 3 else str(marca).upper().ljust(3, 'X')
    return f"{marca_prefix}-{str(item_id).zfill(5)}"

def process_and_unify(json_data, marca):
    """
    Recibe la lista de diccionarios, genera el SKU y unifica en la BD local.
    """
    conn = get_connection()
    c = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserts = 0
    updates = 0

    for item in json_data:
        cod_prov = str(item.get('codigo_proveedor', '')).strip()
        desc = str(item.get('descripcion', '')).strip()
        # Handling Latin American format vs US format securely
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

        # Intentar actualizar primero (UPSERT logic cruzando por Marca y Codigo)
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

    # ---------------- SIDEBAR: CONFIGURACIÓN ----------------
    with st.sidebar:
        st.header("Configuración de Motor IA")
        api_key = st.text_input("Gemini API Key", type="password")
        if not api_key:
            st.warning("⚠️ Ingresa tu API Key para activar el motor de extracción.")

    # ---------------- MAIN UI ----------------
    st.title("Sistema de Extracción IA y Unificación (Barter Plus)")

    st.subheader("1. Embudo de Extracción Masiva")
    st.info("Sube uno o múltiples archivos Excel. La Inteligencia Artificial limpiará los datos automáticamente.")

    uploaded_files = st.file_uploader("Sube Listas de Proveedores (Excel)", type=["xlsx", "xls"], accept_multiple_files=True)

    if uploaded_files:
        st.write("### Asignación de Marca")
        file_marcas = {}
        # Solicitamos la Marca correspondiente para cada archivo subido
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

                with st.spinner(f"Extrayendo texto crudo de {file.name}..."):
                    text_chunks = extract_raw_text_from_excel(file)

                for chunk in text_chunks:
                    with st.spinner(f"({file.name}) Enviando bloque a la IA (gemini-1.5-flash)..."):
                        json_data = call_gemini_engine(chunk, api_key)

                        if json_data:
                            ins, upd = process_and_unify(json_data, marca)
                            all_inserts += ins
                            all_updates += upd

                        # Pequeña pausa para no saturar los rate limits de la API gratuita
                        time.sleep(2)

                progress_bar.progress((i + 1) / len(uploaded_files))

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
