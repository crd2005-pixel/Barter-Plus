import streamlit as st
import sqlite3
import pandas as pd
import requests
import json
import io
import time
from datetime import datetime
import PyPDF2
import re
import os
import shutil
import logging
import sys
import traceback

if getattr(sys, 'frozen', False):
    INSTALL_DIR = os.path.dirname(sys.executable)
else:
    INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    log_path = os.path.join(INSTALL_DIR, 'error_log.txt')
    logging.basicConfig(
        filename=log_path,
        filemode='a',
        level=logging.ERROR,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
except Exception:
    pass

def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = global_exception_handler

def run_migration_barterplus():
    APP_DIR = os.environ.get('APPDATA', os.path.expanduser('~/AppData/Roaming'))
    APP_DIR = os.path.join(APP_DIR, 'BarterPlus')
    os.makedirs(APP_DIR, exist_ok=True)
    db_path = os.path.join(APP_DIR, 'barterplus.db')
    backup_path = os.path.join(APP_DIR, 'barterplus_backup.db')

    if os.path.exists(db_path):
        try:
            shutil.copy2(db_path, backup_path)

            if os.path.exists(backup_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                try:
                    cursor.execute("PRAGMA table_info(productos)")
                    columns = [info[1] for info in cursor.fetchall()]

                    if "codigo_proveedor" not in columns:
                        cursor.execute("ALTER TABLE productos ADD COLUMN codigo_proveedor TEXT;")
                    if "equivalencias" not in columns:
                        cursor.execute("ALTER TABLE productos ADD COLUMN equivalencias TEXT;")

                    conn.commit()
                except Exception as e:
                    pass
                finally:
                    conn.close()
        except Exception as e:
            pass

run_migration_barterplus()

DB_NAME = os.path.join(INSTALL_DIR, "inventario_barter.db")

@st.cache_resource
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS productos_maestro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_interno TEXT UNIQUE,
            proveedor TEXT,
            codigo_proveedor TEXT,
            descripcion TEXT,
            marca TEXT,
            costo_neto REAL,
            contenido_caja TEXT,
            fecha_actualizacion TEXT,
            UNIQUE(proveedor, codigo_proveedor)
        )
    ''')
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_NAME)

def extract_raw_text(uploaded_file, batch_size=50):
    """
    Bifurcación de Extracción: Maneja Excel y PDF.
    Devuelve una lista de chunks (lotes) de texto.
    """
    text_chunks = []
    filename = uploaded_file.name.lower()

    try:
        if filename.endswith(('.xls', '.xlsx')):
            xl = pd.ExcelFile(uploaded_file)
            for sheet in xl.sheet_names:
                df = pd.read_excel(xl, sheet_name=sheet, header=None)
                df = df.dropna(how='all')
                df = df.fillna('')

                for start_idx in range(0, len(df), batch_size):
                    df_chunk = df.iloc[start_idx:start_idx + batch_size]
                    csv_str = df_chunk.to_csv(index=False, header=False)
                    chunk_context = f"--- PESTAÑA ORIGEN: {sheet} ---\n{csv_str}"
                    text_chunks.append(chunk_context)

        elif filename.endswith('.pdf'):
            reader = PyPDF2.PdfReader(uploaded_file)
            all_lines = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    lines = text.split('\n')
                    for line in lines:
                        if line.strip():
                            all_lines.append(line.strip())

            for start_idx in range(0, len(all_lines), batch_size):
                chunk_lines = all_lines[start_idx:start_idx + batch_size]
                chunk_text = "\n".join(chunk_lines)
                chunk_context = f"--- LOTE PDF ---\n{chunk_text}"
                text_chunks.append(chunk_context)

    except Exception as e:
        logging.error(f"Error extrayendo texto del archivo {filename}: {e}\n{traceback.format_exc()}")
        st.error(f"Error extrayendo texto del archivo: {e}")

    return text_chunks

def call_gemini_engine(text_data, api_key, batch_num):
    # API Stateless execution constraint: The HTTP REST architecture natively isolates every request, preventing cross-chunk memory bleeding.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}"
    prompt = "Extrae los productos con sus precios exactos, respetando estrictamente el orden secuencial del texto. ES CRÍTICO QUE NO TRUNQUES LA LISTA: debes devolver el 100% de los ítems encontrados en el texto sin omitir ninguno. Devuelve ÚNICAMENTE un JSON. Para la clave 'marca', debes deducirla del contexto, títulos o descripción. Si es imposible deducirla, pon 'GENERICA'. Extrae el precio (costo_neto) como string sin alterar su formato original.\n\nTexto sucio:\n"

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt + text_data}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "codigo_proveedor": {"type": "STRING"},
                        "marca": {"type": "STRING"},
                        "descripcion": {"type": "STRING"},
                        "costo_neto": {"type": "STRING"},
                        "contenido_caja": {"type": "STRING"}
                    },
                    "required": ["codigo_proveedor", "marca", "descripcion", "costo_neto", "contenido_caja"]
                }
            }
        }
    }

    while True:
        raw_output = ""
        try:
            response = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload)

            if response.status_code == 429:
                st.warning(f"Límite de velocidad de la API alcanzado en el Lote {batch_num}. Enfriando motor por 60 segundos... No cierres el programa.")
                time.sleep(60)
                continue

            if response.status_code != 200:
                st.warning(f"Error de la API en el Lote {batch_num} (HTTP {response.status_code}). Reintentando en 10 segundos...")
                time.sleep(10)
                continue

            response_json = response.json()

            try:
                raw_output = response_json['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError):
                st.warning(f"La API devolvió una respuesta con formato inesperado en el Lote {batch_num}. Reintentando en 10 segundos...")
                time.sleep(10)
                continue

            raw_output = raw_output.replace('```json', '').replace('```', '').strip()

            data = json.loads(raw_output)
            return data

        except json.JSONDecodeError as e:
            logging.error(f"Error JSONDecodeError en Lote {batch_num}: {e}")
            st.warning(f"Error: La IA no devolvió un JSON válido en el Lote {batch_num} (Truncamiento). Reintentando en 10 segundos...")
            time.sleep(10)
            continue
        except Exception as e:
            logging.error(f"Error llamando a Gemini API en Lote {batch_num}: {e}\n{traceback.format_exc()}")
            st.warning(f"Error llamando a la API de Gemini (REST) en el Lote {batch_num}: {e}. Reintentando en 10 segundos...")
            time.sleep(10)
            continue

def limpiar_precio_argentino(valor_crudo):
    import re
    if not isinstance(valor_crudo, str):
        try:
            return float(valor_crudo)
        except (ValueError, TypeError):
            return 0.0

    # Eliminar letras, signos $ y espacios
    s = re.sub(r'[^\d.,]', '', str(valor_crudo).strip())
    if not s:
        return 0.0

    # Si tiene punto y coma, el último es el separador decimal
    if '.' in s and ',' in s:
        if s.rfind(',') > s.rfind('.'): # Ej: 1.500,50
            s = s.replace('.', '').replace(',', '.')
        else: # Ej: 1,500.50
            s = s.replace(',', '')
    elif ',' in s: # Ej: 1500,50
        s = s.replace(',', '.')
    elif '.' in s: # Ej: 1.500 o 1500.50
        partes = s.split('.')
        # Si exactamente 3 dígitos siguen al último punto, es separador de miles ARS
        if len(partes) > 1 and len(partes[-1]) == 3:
            s = s.replace('.', '')
        # Si son 1 o 2 dígitos, se asume decimal y se deja el punto intacto

    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0

import hashlib

def normalize_text(text):
    if not isinstance(text, str): return ""
    text = text.lower()
    text = text.replace('-', ' ').replace('_', ' ').replace('/', ' ')
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def generate_sku(proveedor, codigo_proveedor, marca, descripcion):
    prov_prefix = str(proveedor)[:3].upper() if len(str(proveedor)) >= 3 else str(proveedor).upper().ljust(3, 'X')

    cod = str(codigo_proveedor).strip()
    if cod:
        cod_clean = re.sub(r'[^A-Za-z0-9]', '', cod)
        return f"{prov_prefix}-{cod_clean}"
    else:
        base_str = f"{proveedor}{marca}{descripcion}".encode('utf-8')
        md5_hash = hashlib.md5(base_str).hexdigest()[:8].upper()
        return f"{prov_prefix}-{md5_hash}"


def get_master_lookup(df_master):
    lookup_cod = {}
    lookup_desc = {}
    if df_master is not None and not df_master.empty:
        desc_col = next((c for c in df_master.columns if 'descripci' in c.lower() or 'nombre' in c.lower()), None)
        sku_col = next((c for c in df_master.columns if ('codigo' in c.lower() or 'sku' in c.lower()) and 'proveedor' not in c.lower()), None)

        # Buscar explícitamente codigo_proveedor
        prov_col = next((c for c in df_master.columns if 'codigo_proveedor' in c.lower()), None)
        # Si no lo encuentra, intentar con algo que tenga proveedor pero que parezca código
        if not prov_col:
            prov_col = next((c for c in df_master.columns if 'proveedor' in c.lower() and 'cod' in c.lower()), None)

        if sku_col:
            for _, row in df_master.iterrows():
                sku_val = str(row[sku_col])

                # Cargar por codigo de proveedor (prioridad)
                if prov_col and pd.notna(row[prov_col]):
                    cod_val = str(row[prov_col]).strip().upper()
                    if cod_val:
                        lookup_cod[cod_val] = sku_val

                # Cargar por descripcion (respaldo)
                if desc_col and pd.notna(row[desc_col]):
                    norm_desc = normalize_text(str(row[desc_col]))
                    if norm_desc:
                        lookup_desc[norm_desc] = sku_val

    return lookup_cod, lookup_desc

def process_and_unify(json_data, proveedor, marca_default='', master_lookup_cod=None, master_lookup_desc=None):
    if master_lookup_cod is None:
        master_lookup_cod = {}
    if master_lookup_desc is None:
        master_lookup_desc = {}

    try:
        conn = get_connection()
        c = conn.cursor()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        inserts = 0
        updates = 0

        known_brands = ['WEGA', 'BOSCH', 'MANN', 'FRAM', 'MAHLE', 'SHELL', 'YPF', 'CASTROL', 'TOTAL', 'ELF', 'MOTUL', 'VALVOLINE', 'PETRONAS', 'LIQUI MOLY']

        # Pre-cargar SKUs existentes en memoria para evitar colisiones
        c.execute("SELECT sku_interno FROM productos_maestro")
        used_skus = {row[0] for row in c.fetchall() if row[0]}

        for item in json_data:
            cod_prov = str(item.get('codigo_proveedor', '')).strip()
            desc = str(item.get('descripcion', '')).strip()
            marca = str(item.get('marca', '')).strip().upper()

            if not marca or marca == 'GENERICA':
                if marca_default:
                    marca = marca_default.upper()
                else:
                    marca = 'GENERICA'
                    for b in known_brands:
                        if re.search(r'\b' + re.escape(b) + r'\b', desc, re.IGNORECASE):
                            marca = b
                            break

            costo = limpiar_precio_argentino(item.get('costo_neto', '0'))
            caja = str(item.get('contenido_caja', '1')).strip()

            if not desc:
                logging.warning(f"Fila saltada por falta de descripcion. Datos crudos: {item}")
                continue

            if costo == 0.0:
                logging.warning(f"Advertencia: Producto procesado con precio 0. Datos crudos: {item}")

            norm_desc = normalize_text(desc)
            cod_prov_limpio = str(item.get('codigo_proveedor', '')).strip().upper()

            target_sku = None
            if cod_prov_limpio and cod_prov_limpio in master_lookup_cod:
                target_sku = master_lookup_cod[cod_prov_limpio]
            elif norm_desc in master_lookup_desc:
                target_sku = master_lookup_desc[norm_desc]

            if target_sku:
                final_sku = target_sku
            else:
                base_sku = generate_sku(proveedor, cod_prov, marca, desc)
                final_sku = base_sku
                counter = 1
                while final_sku in used_skus:
                    final_sku = f"{base_sku}-{counter}"
                    counter += 1

            used_skus.add(final_sku)
            if cod_prov_limpio:
                master_lookup_cod[cod_prov_limpio] = final_sku
            master_lookup_desc[norm_desc] = final_sku

            c.execute('''INSERT INTO productos_maestro
                         (proveedor, codigo_proveedor, descripcion, marca, costo_neto, contenido_caja, fecha_actualizacion, sku_interno)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                         ON CONFLICT(sku_interno) DO UPDATE SET
                         costo_neto=excluded.costo_neto,
                         fecha_actualizacion=excluded.fecha_actualizacion,
                         proveedor=excluded.proveedor,
                         codigo_proveedor=excluded.codigo_proveedor,
                         descripcion=excluded.descripcion,
                         marca=excluded.marca''',
                         (proveedor, cod_prov, desc, marca, costo, caja, now, final_sku))
            inserts += 1

        conn.commit()
    except Exception as e:
        logging.error(f"Error fatal en process_and_unify: {e}\n{traceback.format_exc()}")
        raise
    finally:
        if 'conn' in locals() and conn:
            conn.close()

    return inserts, updates

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario Maestro')
    return output.getvalue()

def main():
    st.set_page_config(page_title="Embudo IA Dual (Barter Plus)", layout="wide")
    init_db()

    api_key_default = ""
    api_key_path = os.path.join(INSTALL_DIR, 'api_key.txt')
    if os.path.exists(api_key_path):
        try:
            with open(api_key_path, 'r') as f:
                api_key_default = f.read().strip()
        except Exception:
            pass

    with st.sidebar:
        st.header("Configuración de Motor IA")
        api_key = st.text_input("Gemini API Key", value=api_key_default, type="password")
        if not api_key:
            st.warning("⚠️ Ingresa tu API Key para activar el motor de extracción.")

    st.title("Sistema de Extracción IA Dual y Unificación (Barter Plus)")

    st.subheader("1. Configuración de Base Maestra (Barter Plus)")
    st.info("Selecciona la Base de Datos Maestra para evitar duplicados y proteger códigos internos.")

    master_db_mode = st.radio("Fuente de Base Maestra", ["Conexión Local (barterplus.db)", "Subir Archivo (Excel/CSV)"])
    df_master = None
    master_lookup_cod = {}
    master_lookup_desc = {}

    # Pre-Load forzado desde la base maestra local (productos_maestro) para garantizar memoria caliente
    try:
        conn_local = get_connection()
        cursor_local = conn_local.cursor()
        cursor_local.execute("SELECT sku_interno, codigo_proveedor FROM productos_maestro WHERE codigo_proveedor IS NOT NULL AND codigo_proveedor != ''")
        for row in cursor_local.fetchall():
            sku, cod_prov = row
            master_lookup_cod[str(cod_prov).strip().upper()] = sku
        conn_local.close()
    except Exception as e:
        logging.error(f"Error en Pre-Load de productos_maestro: {e}\n{traceback.format_exc()}")

    if master_db_mode == "Conexión Local (barterplus.db)":
        APP_DIR = os.environ.get('APPDATA', os.path.expanduser('~/AppData/Roaming'))
        db_path = os.path.join(APP_DIR, 'BarterPlus', 'barterplus.db')
        if os.path.exists(db_path):
            st.success(f"Base de datos local detectada: {db_path}")
            try:
                conn_bp = sqlite3.connect(db_path)
                # Seleccionar la tabla completa para permitir la detección dinámica de la columna de SKU alfanumérico (ej. codigo o sku_interno)
                df_master = pd.read_sql_query("SELECT * FROM productos", conn_bp)
                conn_bp.close()
                st.write(f"✓ {len(df_master)} productos cargados para matching.")
                lc, ld = get_master_lookup(df_master)
                master_lookup_cod.update(lc)
                master_lookup_desc.update(ld)
            except Exception as e:
                st.error(f"Error leyendo base local: {e}")
        else:
            st.warning("No se encontró barterplus.db localmente. Procede sin matching o sube un archivo.")
    else:
        master_file = st.file_uploader("Sube la Base Maestra (Excel o CSV)", type=["xlsx", "csv"])
        if master_file:
            try:
                if master_file.name.endswith('.csv'):
                    df_master = pd.read_csv(master_file)
                else:
                    df_master = pd.read_excel(master_file)
                st.write(f"✓ {len(df_master)} productos cargados para matching.")
                lc, ld = get_master_lookup(df_master)
                master_lookup_cod.update(lc)
                master_lookup_desc.update(ld)
            except Exception as e:
                st.error(f"Error leyendo el archivo: {e}")

    st.write("---")
    st.subheader("2. Embudo de Extracción Masiva Multimarca (Excel y PDF)")
    st.info("Sube uno o múltiples archivos (Excel o PDF). La Inteligencia Artificial extraerá y cotejará la información.")

    uploaded_files = st.file_uploader("Sube Listas de Proveedores", type=["xlsx", "xls", "pdf"], accept_multiple_files=True)

    if uploaded_files:
        st.write("### Asignación de Proveedor")
        file_proveedores = {}
        file_marcas = {}
        for file in uploaded_files:
            col1, col2 = st.columns(2)
            with col1:
                file_proveedores[file.name] = st.text_input(f"Proveedor para: {file.name}", key=f"prov_{file.name}").strip().upper()
            with col2:
                file_marcas[file.name] = st.text_input(f"Marca Default (Opcional) para: {file.name}", key=f"marca_{file.name}").strip().upper()

        if st.button("Ejecutar Motor IA y Unificar"):
            if not api_key:
                st.error("No se puede procesar sin una API Key válida.")
                st.stop()

            all_inserts = 0
            all_updates = 0

            progress_bar = st.progress(0)

            for i, file in enumerate(uploaded_files):
                # Flush Memory for each file explicitly
                master_json_list = []
                text_chunks = []

                proveedor = file_proveedores[file.name]
                if not proveedor:
                    st.warning(f"Saltando {file.name}: No se especificó el proveedor.")
                    continue

                with st.spinner(f"[{file.name}] Extrayendo texto crudo y separando en lotes..."):
                    text_chunks = extract_raw_text(file, batch_size=50)

                total_chunks = len(text_chunks)

                for idx, chunk in enumerate(text_chunks):
                    with st.spinner(f"[{file.name}] Procesando Lote {idx + 1} de {total_chunks} mediante IA..."):
                        json_data = call_gemini_engine(chunk, api_key, batch_num=(idx + 1))

                        if json_data:
                            master_json_list.extend(json_data)

                        total_files = len(uploaded_files)
                        base_progress = i / total_files
                        chunk_progress = ((idx + 1) / total_chunks) / total_files
                        progress_bar.progress(base_progress + chunk_progress)

                        time.sleep(4)

                if master_json_list:
                    with st.spinner(f"[{file.name}] Cotejando y unificando resultados..."):

                        marca_def = file_marcas[file.name]
                        ins, upd = process_and_unify(master_json_list, proveedor, marca_def, master_lookup_cod, master_lookup_desc)
                        all_inserts += ins
                        all_updates += upd

            st.success(f"✅ ¡Proceso de Embudo IA finalizado! Productos Nuevos (Creados): {all_inserts} | Productos Actualizados (Matching): {all_updates}")

    st.write("---")
    st.subheader("3. Inventario Maestro (Exportación Final)")

    conn = get_connection()
    df_maestro = pd.read_sql_query("SELECT sku_interno, proveedor, codigo_proveedor, descripcion, marca, costo_neto, contenido_caja, fecha_actualizacion FROM productos_maestro", conn)
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
