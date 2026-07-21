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

class IngestaInteligenteLubricentro:
    def __init__(self, maestro_db_path="inventario_barter.db"):
        self.maestro_db_path = maestro_db_path
        self.alias_costo = r"(pr.*icio|costo|arancel|neto|uni.*tario).*"
        self.alias_desc = r"(det.*alle|art.*iculo|desc.*ripcion|prod.*ucto).*"
        self.alias_cod = r"(cod.*igo|cod|ref).*"

    def purgar_basura_operativa(self, df):
        """Elimina filas vacías, metadata y títulos intermedios."""
        # 1. Eliminar filas 100% vacías
        df = df.dropna(how='all')
        if df.empty:
            return df

        # 2. Eliminar metadata (filas con palabras clave de gestión, no comerciales)
        basura_regex = r"(vigencia|pagina|lista de|proveedor|s\.a\.|RAMONSABIO|LISTA SUJETA A CAMBIOS|NO INCLUYE IVA|VÁLIDA HASTA|CONFIRMAR PRECIOS|SOLO CONTADO)"
        # Revisamos la primera columna como indicadora de metadata
        mask_basura = df.iloc[:, 0].astype(str).str.contains(basura_regex, case=False, na=False)
        df = df[~mask_basura]

        return df

    def detectar_y_separar_tablas_apiladas(self, df_hoja, sheet_name=""):
        """Detecta si una hoja tiene múltiples tablas una sobre otra."""
        tablas_detectadas = []

        # Si la hoja está vacía tras purgar basura
        if df_hoja.empty: return tablas_detectadas

        # Por simplicidad en este script, mapeamos la primera tabla y purgar títulos internos.
        # Normalizamos encabezados de la primera tabla encontrada
        df_hoja = self.normalizar_encabezados(df_hoja)
        if not df_hoja.empty:
            df_hoja['marca_sugerida'] = sheet_name.strip().upper()
            tablas_detectadas.append(df_hoja)

        return tablas_detectadas

    def normalizar_encabezados(self, df):
        """Usa Smart Alias para unificar columnas basadas en Regex."""
        # If columns are just integers (no header row specified in read_excel), we need to find the header row.
        # For simplicity, we try to match the current columns or the first few rows.

        header_row_index = -1
        new_headers = {}

        # Check first 10 rows to find a valid header
        for idx in range(min(10, len(df))):
            row_vals = [str(x).lower().strip() for x in df.iloc[idx]]
            temp_headers = {}
            for i, h_str in enumerate(row_vals):
                if re.match(self.alias_costo, h_str):
                    temp_headers[df.columns[i]] = 'costo_unificado'
                elif re.match(self.alias_desc, h_str):
                    temp_headers[df.columns[i]] = 'descripcion_unificada'
                elif re.match(self.alias_cod, h_str):
                    temp_headers[df.columns[i]] = 'codigo_unificado'

            if 'descripcion_unificada' in temp_headers.values() and 'costo_unificado' in temp_headers.values():
                header_row_index = idx
                new_headers = temp_headers
                break

        if header_row_index != -1:
            # We found a header row, so we rename and then drop rows up to and including the header
            df = df.rename(columns=new_headers)
            df = df.iloc[header_row_index+1:].copy()
        else:
            # Maybe columns were already set (e.g. read_excel with header=0)
            headers = df.columns.tolist()
            for header in headers:
                h_str = str(header).lower().strip()
                if re.match(self.alias_costo, h_str):
                    new_headers[header] = 'costo_unificado'
                elif re.match(self.alias_desc, h_str):
                    new_headers[header] = 'descripcion_unificada'
                elif re.match(self.alias_cod, h_str):
                    new_headers[header] = 'codigo_unificado'
            df = df.rename(columns=new_headers)

        # Filtramos para quedarnos solo con las columnas unificadas críticas
        columnas_criticas = ['codigo_unificado', 'descripcion_unificada', 'costo_unificado']
        columnas_a_mantener = [c for c in columnas_criticas if c in df.columns]

        if len(columnas_a_mantener) < 2: # Si no encontramos al menos Descripción y Costo, no es tabla válida
            return pd.DataFrame()

        return df[columnas_a_mantener]

    def sanitizar_datos_finales(self, df):
        """Corrige errores de dato (texto en precio) y normaliza."""
        if df.empty: return df

        # 1. Convertir costo a numérico, forzando errores a NaN (luego a 0)
        df['costo_unificado'] = pd.to_numeric(df['costo_unificado'].astype(str).str.replace(',', '.').str.replace('$', '').str.strip(), errors='coerce').fillna(0)

        # 2. Limpiar espacios en códigos y descripciones
        if 'codigo_unificado' in df.columns:
            df['codigo_unificado'] = df['codigo_unificado'].astype(str).str.strip().str.upper()
        if 'descripcion_unificada' in df.columns:
            df['descripcion_unificada'] = df['descripcion_unificada'].astype(str).str.strip()

        return df

    def procesar_excel_completo(self, excel_file_obj):
        """Módulo Principal: Lee multi-pestañas, purga, unifica y normaliza."""
        try:
            excel_file = pd.ExcelFile(excel_file_obj)
            all_sheets_unified = []

            for sheet_name in excel_file.sheet_names:
                df_sheet = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)

                # Fase 2: Purga Basura
                df_clean = self.purgar_basura_operativa(df_sheet)

                # Fase 3 y 4: De-Stacker y Normalizar Encabezados
                tablas_de_hoja = self.detectar_y_separar_tablas_apiladas(df_clean, sheet_name)

                for tabla in tablas_de_hoja:
                    if not tabla.empty:
                        # Fase 5: Normalizar Datos
                        tabla_final = self.sanitizar_datos_finales(tabla)
                        all_sheets_unified.append(tabla_final)

            if not all_sheets_unified:
                print("❌ No se encontraron tablas comerciales válidas en el archivo.")
                return pd.DataFrame()

            # Unificación Final de todas las pestañas y tablas stackeadas
            df_maestro_unificado = pd.concat(all_sheets_unified, ignore_index=True)
            print(f"✅ Unificación masiva completada. {len(df_maestro_unificado)} productos normalizados.")
            return df_maestro_unificado

        except Exception as e:
            print(f"❌ Error crítico en ingesta: {e}")
            return pd.DataFrame()

    def procesar_pdf(self, pdf_file_obj, marca):
        """Procesa un PDF usando la misma normalización."""
        try:
            data = []
            with pdfplumber.open(pdf_file_obj) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        data.extend(table)
            if not data:
                return pd.DataFrame()

            df_sheet = pd.DataFrame(data)
            df_clean = self.purgar_basura_operativa(df_sheet)
            tablas_de_hoja = self.detectar_y_separar_tablas_apiladas(df_clean, marca)

            all_tables = []
            for tabla in tablas_de_hoja:
                if not tabla.empty:
                    tabla_final = self.sanitizar_datos_finales(tabla)
                    all_tables.append(tabla_final)

            if all_tables:
                return pd.concat(all_tables, ignore_index=True)
            return pd.DataFrame()
        except Exception as e:
            print(f"❌ Error crítico en ingesta PDF: {e}")
            return pd.DataFrame()

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
    marca_prefix = str(marca)[:3].upper() if len(str(marca)) >= 3 else str(marca).upper().ljust(3, 'X')
    tipo_code = "UN" if tipo_venta == "UNIDAD" else "GR"
    return f"{marca_prefix}-{tipo_code}-{str(item_id).zfill(5)}"

def process_mass_update(df_unified):
    """
    Procesa un dataframe unificado e inserta/actualiza en la base de datos maestra.
    Cruza por Marca y Tipo de Venta.
    """
    conn = get_connection()
    c = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updates = 0
    inserts = 0

    c.execute("SELECT id, codigo_proveedor, descripcion, tipo_venta, marca FROM productos_maestro")
    db_items_all = c.fetchall()

    for _, row in df_unified.iterrows():
        cod_prov = str(row.get('codigo_unificado', '')).strip() if 'codigo_unificado' in df_unified.columns and pd.notna(row.get('codigo_unificado')) else ""
        desc = str(row.get('descripcion_unificada', '')).strip() if 'descripcion_unificada' in df_unified.columns and pd.notna(row.get('descripcion_unificada')) else ""
        costo = row.get('costo_unificado', 0.0) if 'costo_unificado' in df_unified.columns else 0.0
        marca = str(row.get('marca_sugerida', '')).strip().upper() if 'marca_sugerida' in df_unified.columns else ""
        caja = "1" # El módulo IngestaInteligente no extrae caja por ahora

        if not desc or desc.lower() in ['nan', 'none', '']:
            continue

        tipo_venta = detect_unit_and_capacity(desc)
        matched_id = None

        # Filter DB items by brand for this specific row
        db_items = [item for item in db_items_all if item[4] == marca]

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

            new_record = (new_id, cod_prov, desc, tipo_venta, marca)
            db_items_all.append(new_record)
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
    st.set_page_config(page_title="Gestor Resiliente y Entrenable", layout="wide")

    run_init_db()

    # ---------------- MAIN UI: INGESTA MINIMALISTA ----------------
    st.title("Sistema de Ingesta Inteligente Lubricentro")

    st.subheader("1. Ingesta Masiva y Mapeo Automático")
    col1, col2 = st.columns(2)

    with col1:
        update_file = st.file_uploader("Sube Lista Nueva (Excel o PDF)", type=["xlsx", "xls", "pdf"], key="update_file")
    with col2:
        marca_manual_pdf = st.text_input("Ingresa la MARCA (Requerido solo para PDFs):", key="marca_pdf").strip().upper()

    if update_file:
        if st.button("Procesar Lista"):
            filename = update_file.name.lower()
            ingesta = IngestaInteligenteLubricentro()
            df_unificado = pd.DataFrame()

            if filename.endswith(('.xls', '.xlsx')):
                with st.spinner("Procesando Excel masivamente y mapeando automáticamente..."):
                    df_unificado = ingesta.procesar_excel_completo(update_file)
            elif filename.endswith('.pdf'):
                if not marca_manual_pdf:
                    st.error("Debes ingresar la Marca para procesar un PDF.")
                    st.stop()
                with st.spinner("Procesando PDF y mapeando automáticamente..."):
                    df_unificado = ingesta.procesar_pdf(update_file, marca_manual_pdf)

            if not df_unificado.empty:
                st.write("### Datos Normalizados (Pre-Fuzzy Matching)")
                st.dataframe(df_unificado.head(15))
                with st.spinner(f"Filas normalizadas: {len(df_unificado)}. Ejecutando Inteligencia de Matching en la BD..."):
                    ins, upd = process_mass_update(df_unificado)
                    st.success(f"✅ ¡Completado! Creados: {ins} | Actualizados: {upd}")
            else:
                st.error("El Parser no detectó tablas comerciales válidas (faltan las columnas Código, Descripción o Precio).")

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
