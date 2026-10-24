import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sqlite3
import pandas as pd
import pdfplumber
import os
import re
import json
import math
from datetime import datetime
import hashlib
from typing import List, Optional
from pydantic import BaseModel, Field
from difflib import SequenceMatcher
try:
    from google import genai
except ImportError:
    genai = None

PATRON_MEMBRETE = re.compile(
    r'(tel\s*[:.]?|cel\s*[:.]?|fax|0260|0261|44\d[\s-]?\d{3}|sarmiento|san\s+rafael|mendoza|cuit|iva\s|www\.|http|@|distribuidora|hoja\s*\d|p[aá]gina)',
    re.IGNORECASE
)

# App Config
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def extraer_productos_dinamico_multimodal(ruta_archivo: str, proveedor: str, api_key: str, tipo_archivo: str, page_num: int = None, pdf_bytes: bytes = None) -> list:
    if not genai or not api_key:
        return []

    client = genai.Client(api_key=api_key)

    class ProductoExtraido(BaseModel):
        codigo_proveedor: str = Field(description="El código real del artículo. PROHIBIDO que empiece con '$' o sea un importe.")
        descripcion: str = Field(description="Nombre completo, tipo de producto, medidas, aplicación. PROHIBIDO incluir direcciones, teléfonos, o precios.")
        marca: str = Field(description="La marca real del artículo detectada en la fila, columna o sección.")
        costo: float = Field(description="El precio unitario final numérico puro (tomar el precio final y omitir valores parciales o entregas de cascos).")

    class ListaProductos(BaseModel):
        productos: List[ProductoExtraido]

    prompt_texto = f"""
    Eres un extractor determinista de listas de precios para el proveedor '{proveedor}'.
    Extrae estrictamente los productos de la imagen o documento adjunto.

    REGLAS ESTRICTAS:
    1. Si una celda o fila agrupa varios códigos apilados verticalmente con sus respectivos amperajes, marcas y precios (como en listas de baterías), desglosa cada código como un producto individual alineando su marca, amperaje, aplicación compartida y su precio correspondiente.
    2. Si una tabla tiene el precio en una columna central y códigos de equivalencia (MANN, FRAM, WEGA, MARENO) a la derecha, toma el precio de la columna Precio e incluye las equivalencias dentro de la descripción.
    3. Ignora membretes comerciales, teléfonos, direcciones, descuentos generales de cabecera y números de página.
    4. Jamás permitas que un código de proveedor contenga el símbolo "$" o parezca un precio.
    5. Jamás permitas que la descripción contenga valores monetarios aislados sin contexto.
    """

    try:
        if tipo_archivo == 'pdf' and pdf_bytes:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    genai.types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    prompt_texto
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ListaProductos
                )
            )
        elif tipo_archivo == 'excel' and pdf_bytes: # Re-using bytes variable for text in excel
             response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    pdf_bytes, # Treat as text block for excel fallback
                    prompt_texto
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ListaProductos
                )
            )
        else:
            return []

        data = json.loads(response.text)

        extracted = []
        origen = f"Pag {page_num+1}" if page_num is not None else "Documento"

        for item in data.get('productos', []):
            extracted.append({
                'proveedor': proveedor,
                'codigo_proveedor': item.get('codigo_proveedor', ''),
                'descripcion': item.get('descripcion', ''),
                'marca': item.get('marca', 'GENERICA'),
                'costo_neto': item.get('costo', 0.0),
                'origen': origen
            })

        return extracted
    except Exception as e:
        import traceback
        print("Error multimodal:", traceback.format_exc())
        return []

def extraer_productos_de_pdf(ruta_pdf: str, proveedor: str, api_key: str) -> list:
    extracted_total = []

    try:
        import fitz # PyMuPDF for efficient page by page bytes extraction if needed, but we'll use open read
        with open(ruta_pdf, 'rb') as f:
            pdf_bytes = f.read()

        # Send entire PDF (up to limits) or split. For now send whole PDF if small enough, or iterate.
        # GenAI Flash supports large contexts, sending the whole PDF binary is acceptable for many cases.
        # But we were instructed to divide or process in blocks of 1-2 pages or send binary.
        # Let's send the binary directly as requested: `types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")`

        extracted_list = extraer_productos_dinamico_multimodal(ruta_pdf, proveedor, api_key, 'pdf', page_num=0, pdf_bytes=pdf_bytes)

        # Validation Candado Determinista (post-extraction)
        for prod in extracted_list:
            cod = str(prod['codigo_proveedor']).strip()
            desc = str(prod['descripcion']).strip()
            costo = prod['costo_neto']

            # Reject if code has $ or matches a price format
            if '$' in cod or re.match(r'^\\$?\s*\d{1,3}(?:\.\d{3})+(?:,\d{2})?$', cod):
                continue

            # Reject if description is just a price or empty
            if not desc or desc.startswith("Pag ") and "$" in desc:
                # Basic check, we can refine
                if len(re.sub(r'Pag\s*\d+\s*-\s*\$\s*[\d.,]+', '', desc).strip()) == 0:
                     continue
            if re.match(r'^\\$?\s*\d{1,3}(?:\.\d{3})+(?:,\d{2})?$', desc):
                continue

            # Valid product
            extracted_total.append(prod)

    except Exception as e:
        print(f"Error procesando PDF: {e}")

    return extracted_total





class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Unificador de Listas - Barter Plus")

        appdata = os.environ.get('APPDATA')
        if not appdata:
            appdata = os.path.expanduser('~/AppData/Roaming')
        self.app_dir = os.path.join(appdata, 'BarterPlus_Unificador')
        os.makedirs(self.app_dir, exist_ok=True)

        self.local_db_path = os.path.join(self.app_dir, "unificador_interno.db")
        self.master_db_path = None
        self.api_key = ""

        # Triple Index Maps
        self.mapa_por_cod_prov = {}
        self.mapa_por_sku_sufijo = {}
        self.mapa_por_descripcion = {}

        self.config_file = os.path.join(self.app_dir, "config.json")

        self.init_local_db()
        self.load_config()
        self.auto_connect_master_db()

        self.geometry("1000x750")

        # Icon loading
        try:
            icon_path = os.path.join(sys._MEIPASS, 'ICONO.ico') if hasattr(sys, '_MEIPASS') else os.path.join(os.path.dirname(__file__), 'ICONO.ico')
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        # Grid layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.title_label = ctk.CTkLabel(self.header_frame, text="Unificador de Listas - Motor Determinista", font=("Roboto", 24, "bold"))
        self.title_label.pack(pady=10)

        # Main Tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        self.tab_import = self.tabview.add("1. Importar y Mapear")
        self.tab_audit = self.tabview.add("2. Auditoría Pre-Guardado")
        self.tab_export = self.tabview.add("3. Exportar / BD")

        self.setup_import_tab()
        self.setup_audit_tab()
        self.setup_export_tab()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.master_db_path = config.get('master_db_path')
                    self.api_key = config.get('api_key', "")
            except:
                pass

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump({'master_db_path': self.master_db_path, 'api_key': self.api_key}, f)

    def setup_import_tab(self):
        # API Key Configuration
        self.api_frame = ctk.CTkFrame(self.tab_import)
        self.api_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(self.api_frame, text="Gemini API Key:").pack(side="left", padx=10, pady=5)
        self.entry_api_key = ctk.CTkEntry(self.api_frame, width=300, show="*")
        self.entry_api_key.pack(side="left", padx=5, pady=5)
        if self.api_key:
            self.entry_api_key.insert(0, self.api_key)

        self.btn_save_api = ctk.CTkButton(self.api_frame, text="Guardar Key", command=self.save_api_key)
        self.btn_save_api.pack(side="left", padx=10, pady=5)

        # Master DB Reference Panel
        self.master_frame = ctk.CTkFrame(self.tab_import, fg_color="#1e3a5f") # Distinctive color
        self.master_frame.pack(fill="x", padx=10, pady=5)

        self.lbl_master_info = ctk.CTkLabel(self.master_frame, text="Buscando Base Barter Plus...", font=("Roboto", 14, "bold"), text_color="white")
        self.lbl_master_info.pack(pady=10)

        btn_frame = ctk.CTkFrame(self.master_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=5)

        self.btn_link_db = ctk.CTkButton(btn_frame, text="Vincular Base Manual (.db) [SOLO LECTURA]", command=self.link_master_db)
        self.btn_link_db.pack(side="left", padx=10)

        self.btn_link_excel = ctk.CTkButton(btn_frame, text="O Cargar Padrón desde Excel (.xlsx)", command=self.link_master_excel)
        self.btn_link_excel.pack(side="left", padx=10)

        # Update initial banner text if already loaded
        self.update_master_banner()

        # Frame for file selection & Basic Info
        self.file_frame = ctk.CTkFrame(self.tab_import)
        self.file_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(self.file_frame, text="Proveedor (Obligatorio):").pack(side="left", padx=10)
        self.entry_proveedor = ctk.CTkEntry(self.file_frame, width=150)
        self.entry_proveedor.pack(side="left", padx=5)

        ctk.CTkLabel(self.file_frame, text=" | ").pack(side="left", padx=10)

        ctk.CTkLabel(self.file_frame, text="Archivos del Proveedor:").pack(side="left", padx=10)
        self.btn_load_excel = ctk.CTkButton(self.file_frame, text="Cargar Excel", command=self.load_excel)
        self.btn_load_excel.pack(side="left", padx=5, pady=10)

        self.btn_load_pdf = ctk.CTkButton(self.file_frame, text="Cargar PDF", command=self.load_pdf)
        self.btn_load_pdf.pack(side="left", padx=5, pady=10)

        self.lbl_file_info = ctk.CTkLabel(self.file_frame, text="Ningún archivo cargado")
        self.lbl_file_info.pack(side="left", padx=10, pady=10)

        self.config_frame = ctk.CTkFrame(self.tab_import)
        self.config_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Main Process Frame
        self.map_frame = ctk.CTkFrame(self.config_frame)
        self.map_frame.pack(fill="x", pady=5)

        self.btn_process_file = ctk.CTkButton(self.map_frame, text="Agente IA: Analizar Estructura y Extraer", font=("Roboto", 14, "bold"), command=self.process_file, fg_color="green", height=40)
        self.btn_process_file.pack(side="right", padx=10, pady=10)

        self.btn_select_all_sheets = ctk.CTkButton(self.map_frame, text="Seleccionar Todas las Pestañas", command=self.select_all_sheets)
        self.btn_select_all_sheets.pack(side="left", padx=10, pady=10)

        # Tabs container
        self.sheets_frame = ctk.CTkScrollableFrame(self.config_frame, height=200)
        self.sheets_frame.pack(fill="both", expand=True, pady=5)
        self.sheet_vars = {}

        # Temp list for processing results
        self.extracted_data = []
        self.current_file = None
        self.current_file_type = None
        self.excel_data = None # Dictionary of DataFrames

    def save_api_key(self):
        self.api_key = self.entry_api_key.get().strip()
        self.save_config()
        messagebox.showinfo("Éxito", "Gemini API Key guardada en config.json")

    def select_all_sheets(self):
        for var in self.sheet_vars.values():
            var.set(True)

    def setup_audit_tab(self):
        self.audit_tabview = ctk.CTkTabview(self.tab_audit)
        self.audit_tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_audit_updates = self.audit_tabview.add("Actualizaciones de Precio (Existentes)")
        self.tab_audit_new = self.audit_tabview.add("Productos Nuevos Detectados")

        # Updates Treeview
        columns_updates = ('SKU', 'Cod. Prov.', 'Descripción', 'Costo Ant.', 'Costo Nvo.', 'Var. %')
        self.tree_updates = ttk.Treeview(self.tab_audit_updates, columns=columns_updates, show='headings')
        for col in columns_updates:
            self.tree_updates.heading(col, text=col)
            self.tree_updates.column(col, width=120)
        self.tree_updates.pack(fill="both", expand=True, pady=5)

        # New Treeview
        columns_new = ('Proveedor', 'Cod. Prov.', 'Descripción', 'Marca', 'Costo')
        self.tree_new = ttk.Treeview(self.tab_audit_new, columns=columns_new, show='headings')
        for col in columns_new:
            self.tree_new.heading(col, text=col)
            self.tree_new.column(col, width=120)
        self.tree_new.pack(fill="both", expand=True, pady=5)

        # Tracking lists for DB Upsert
        self.audit_updates_list = []
        self.audit_new_list = []

    def setup_export_tab(self):
        self.export_frame = ctk.CTkFrame(self.tab_export)
        self.export_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.chk_var_new = tk.BooleanVar(value=True)
        self.chk_new = ctk.CTkCheckBox(self.export_frame, text="Incluir Productos Nuevos (Crear SKUs)", variable=self.chk_var_new)
        self.chk_new.pack(pady=20)

        self.btn_export_excel = ctk.CTkButton(self.export_frame, text="Exportar Excel Limpio y Unificado (Para Sistema de Gestión)", font=("Roboto", 16, "bold"), height=50, command=self.export_excel, fg_color="green")
        self.btn_export_excel.pack(pady=15, fill="x", padx=50)

        self.btn_apply_db = ctk.CTkButton(self.export_frame, text="Guardar en Historial del Unificador (Base Propia)", command=self.apply_db_changes)
        self.btn_apply_db.pack(pady=10)

    def auto_connect_master_db(self):
        # 1. Check Config
        if self.master_db_path and os.path.exists(self.master_db_path):
            self.load_master_index_db(self.master_db_path)
            return

        # 2. Check Default BarterPlus paths
        appdata = os.environ.get('APPDATA')
        if not appdata:
            appdata = os.path.expanduser('~/AppData/Roaming')

        paths_to_check = [
            os.path.join(appdata, 'BarterPlus', 'barterplus.db'),
            os.path.join(appdata, 'BarterPlus', 'barterplus')
        ]

        for path in paths_to_check:
            if os.path.exists(path):
                self.master_db_path = path
                self.save_config()
                self.load_master_index_db(path)
                return

    def update_master_banner(self, text=None, is_error=False, detected_cols=None):
        if not hasattr(self, 'lbl_master_info'): return

        if text:
            color = "#ff6b6b" if is_error else "white"
            self.lbl_master_info.configure(text=text, text_color=color)
        elif hasattr(self, 'last_master_table_name') and self.last_master_table_name:
            count = len(self.mapa_por_sku_sufijo)
            col_info = f"Columnas: {detected_cols}" if detected_cols else ""
            msg = f"✅ Base Barter Plus Conectada (Solo Lectura): Tabla '{self.last_master_table_name}' | {count} productos cargados | {col_info}"
            self.lbl_master_info.configure(text=msg, text_color="#2ecc71")
        elif len(self.mapa_por_sku_sufijo) > 0:
            count = len(self.mapa_por_sku_sufijo)
            msg = f"✅ Padrón Excel Conectado: {count} productos cargados"
            self.lbl_master_info.configure(text=msg, text_color="#2ecc71")

    def link_master_db(self):
        file_path = filedialog.askopenfilename(filetypes=[("SQLite DB", "*.db *.sqlite *.sqlite3 *")])
        if not file_path: return
        self.master_db_path = file_path
        self.save_config()
        self.load_master_index_db(file_path)

    def link_master_excel(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx *.xls")])
        if not file_path: return
        try:
            df = pd.read_excel(file_path)
            # Find required columns heuristically
            cols = [str(c).lower() for c in df.columns]

            sku_col = next((c for c in df.columns if 'sku' in str(c).lower()), None)
            prov_col = next((c for c in df.columns if 'proveedor' in str(c).lower() and 'cod' not in str(c).lower()), None)
            cod_col = next((c for c in df.columns if 'cod' in str(c).lower() and 'prov' in str(c).lower()), None)
            if not cod_col: cod_col = next((c for c in df.columns if 'codigo' in str(c).lower()), None)
            desc_col = next((c for c in df.columns if 'desc' in str(c).lower()), None)
            marca_col = next((c for c in df.columns if 'marca' in str(c).lower()), None)
            costo_col = next((c for c in df.columns if 'costo' in str(c).lower() or 'precio' in str(c).lower()), None)

            if not all([sku_col, cod_col, desc_col]):
                messagebox.showerror("Error", "No se detectaron las columnas requeridas (SKU, Codigo, Descripcion) en el Excel.")
                return

            self.mapa_por_cod_prov.clear()
            self.mapa_por_sku_sufijo.clear()
            self.mapa_por_descripcion.clear()

            for idx, row in df.iterrows():
                if pd.isna(row.get(sku_col)): continue
                sku = str(row.get(sku_col)).strip()

                prov = str(row.get(prov_col, '')).strip().upper() if prov_col else 'N/A'
                cod_raw = str(row.get(cod_col, '')).strip()
                desc_raw = str(row.get(desc_col, '')).strip()

                prod_data = {
                    'sku_interno': sku,
                    'descripcion': desc_raw,
                    'marca': str(row.get(marca_col, '')),
                    'costo_neto': float(row.get(costo_col, 0.0)) if costo_col and pd.notna(row.get(costo_col)) else 0.0,
                    'proveedor': prov,
                    'codigo_proveedor': cod_raw
                }

                self.index_product(prod_data, sku, cod_raw, desc_raw)

            self.last_master_table_name = None
            self.update_master_banner()
            self.master_db_path = None # Clear DB path if excel is used
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando Excel maestro: {e}")

    def generate_sku(self, proveedor, codigo_proveedor, marca, descripcion):
        prov_prefix = str(proveedor)[:3].upper() if len(str(proveedor)) >= 3 else str(proveedor).upper().ljust(3, 'X')
        cod = str(codigo_proveedor).strip()
        if cod:
            cod_clean = re.sub(r'[^A-Za-z0-9]', '', cod)
            return f"{prov_prefix}-{cod_clean}"
        else:
            base_str = f"{proveedor}{marca}{descripcion}".encode('utf-8')
            md5_hash = hashlib.md5(base_str).hexdigest()[:8].upper()
            return f"{prov_prefix}-{md5_hash}"

    def apply_db_changes(self):
        if not self.audit_updates_list and not self.audit_new_list:
            messagebox.showinfo("Aviso", "No hay datos para aplicar.")
            return

        if not messagebox.askyesno("Confirmar", "¿Está seguro de aplicar los cambios en la base de datos?"):
            return

        try:
            conn = sqlite3.connect(self.local_db_path)
            c = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            inserts = 0

            # Just store history locally
            for item in self.audit_updates_list:
                c.execute('''INSERT INTO historial_unificador
                             (sku_interno, proveedor, codigo_proveedor, descripcion, marca, costo_neto, fecha_actualizacion)
                             VALUES (?, ?, ?, ?, ?, ?, ?)''',
                          (item['sku_interno'], item.get('proveedor', ''), item['codigo_proveedor'], item['descripcion'], item['marca'], item['costo_nvo'], now))
                inserts += 1

            if self.chk_var_new.get():
                for item in self.audit_new_list:
                    sku = self.generate_sku(item['proveedor'], item['codigo_proveedor'], item['marca'], item['descripcion'])
                    c.execute('''INSERT INTO historial_unificador
                                 (sku_interno, proveedor, codigo_proveedor, descripcion, marca, costo_neto, fecha_actualizacion)
                                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
                              (sku, item['proveedor'], item['codigo_proveedor'], item['descripcion'], item['marca'], item['costo_neto'], now))
                    inserts += 1

            conn.commit()
            conn.close()

            messagebox.showinfo("Éxito", f"Se guardaron {inserts} registros en el historial local.")

            # Clear temp memory
            self.extracted_data.clear()
            self.audit_updates_list.clear()
            self.audit_new_list.clear()
            for item in self.tree_updates.get_children(): self.tree_updates.delete(item)
            for item in self.tree_new.get_children(): self.tree_new.delete(item)

        except Exception as e:
            messagebox.showerror("Error DB", f"Ocurrió un error guardando en DB: {e}")

    def export_excel(self):
        if not self.audit_updates_list and not self.audit_new_list:
            messagebox.showinfo("Aviso", "No hay datos procesados en la auditoría para exportar.")
            return

        try:
            export_data = []

            for item in self.audit_updates_list:
                export_data.append({
                    'sku_interno': item['sku_interno'],
                    'proveedor': item['proveedor'] if 'proveedor' in item else '',
                    'codigo_proveedor': item['codigo_proveedor'],
                    'descripcion': item['descripcion'],
                    'marca': item['marca'],
                    'costo_neto': item['costo_nvo']
                })

            if self.chk_var_new.get():
                for item in self.audit_new_list:
                    sku = self.generate_sku(item['proveedor'], item['codigo_proveedor'], item['marca'], item['descripcion'])
                    export_data.append({
                        'sku_interno': sku,
                        'proveedor': item['proveedor'],
                        'codigo_proveedor': item['codigo_proveedor'],
                        'descripcion': item['descripcion'],
                        'marca': item['marca'],
                        'costo_neto': item['costo_neto']
                    })

            if not export_data:
                messagebox.showinfo("Aviso", "No hay registros para exportar.")
                return

            df = pd.DataFrame(export_data)

            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel Files", "*.xlsx")],
                initialfile="Padrón_Exportado_Limpio.xlsx"
            )

            if file_path:
                df.to_excel(file_path, index=False, engine='openpyxl')
                messagebox.showinfo("Éxito", f"Archivo limpio exportado correctamente a:\n{file_path}\nTotal: {len(df)} registros.")

        except Exception as e:
            messagebox.showerror("Error de Exportación", f"No se pudo exportar a Excel: {e}")

    def init_local_db(self):
        try:
            conn = sqlite3.connect(self.local_db_path)
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS historial_unificador (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku_interno TEXT,
                    proveedor TEXT,
                    codigo_proveedor TEXT,
                    descripcion TEXT,
                    marca TEXT,
                    costo_neto REAL,
                    fecha_actualizacion TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            messagebox.showerror("Error Local DB", f"Error inicializando base de historial: {e}")

    def index_product(self, prod_data, sku, cod_raw, desc_raw):
        # Index 1: By Normalized Code
        if cod_raw and cod_raw.lower() not in ['none', 'null', '']:
            cod_norm = str(cod_raw).strip().upper().replace(" ", "")
            if cod_norm: self.mapa_por_cod_prov[cod_norm] = prod_data

        # Index 2: By SKU Suffix
        if sku:
            parts = str(sku).split('-')
            sufijo = parts[-1].strip().upper().replace(" ", "") if len(parts) > 1 else str(sku).strip().upper().replace(" ", "")
            if sufijo: self.mapa_por_sku_sufijo[sufijo] = prod_data

        # Index 3: By Normalized Description
        if desc_raw and desc_raw.lower() not in ['none', 'null', '']:
            # Replace multiple spaces with single space, uppercase
            desc_norm = re.sub(r'\s+', ' ', str(desc_raw).strip().upper())
            if desc_norm: self.mapa_por_descripcion[desc_norm] = prod_data

    def load_master_index_db(self, db_path):
        try:
            uri = f"file:{os.path.abspath(db_path)}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Heuristically find the products table
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in c.fetchall()]

            table_name = None
            cols = []

            # Heuristically find the products table by looking at columns
            for t in tables:
                c.execute(f"PRAGMA table_info({t})")
                t_cols = [r['name'].lower() for r in c.fetchall()]

                # Check for product-like columns
                has_code = any(c in t_cols for c in ['sku', 'sku_interno', 'codigo', 'codigo_proveedor'])
                has_desc = any(c in t_cols for c in ['descripcion', 'nombre', 'detalle'])
                has_price = any(c in t_cols for c in ['costo', 'costo_neto', 'precio'])

                if has_code and has_desc and has_price:
                    table_name = t
                    cols = t_cols
                    break

            if not table_name:
                self.update_master_banner("Aviso: No se detectó tabla de inventario válida en la DB maestra.", is_error=True)
                conn.close()
                return

            self.last_master_table_name = table_name

            sku_col = 'sku_interno' if 'sku_interno' in cols else ('sku' if 'sku' in cols else 'codigo')
            prov_col = 'proveedor' if 'proveedor' in cols else ('proveedor_id' if 'proveedor_id' in cols else "''")
            cod_col = 'codigo_proveedor' if 'codigo_proveedor' in cols else ('codigo' if 'codigo' in cols else sku_col)
            desc_col = 'descripcion' if 'descripcion' in cols else ('nombre' if 'nombre' in cols else 'detalle')
            marca_col = 'marca' if 'marca' in cols else ('marca_id' if 'marca_id' in cols else "''")
            costo_col = 'costo_neto' if 'costo_neto' in cols else ('costo' if 'costo' in cols else 'precio')

            detected_cols = f"{sku_col}, {cod_col}, {desc_col}, {costo_col}"
            query = f"SELECT {sku_col} as sku_interno, {prov_col} as proveedor, {cod_col} as codigo_proveedor, {desc_col} as descripcion, {marca_col} as marca, {costo_col} as costo_neto FROM {table_name}"

            c.execute(query)
            rows = c.fetchall()

            self.mapa_por_cod_prov.clear()
            self.mapa_por_sku_sufijo.clear()
            self.mapa_por_descripcion.clear()

            for row in rows:
                sku = str(row['sku_interno']).strip()
                # Use 'N/A' if the column wasn't found or if the data is literally missing
                prov = str(row['proveedor']).strip().upper() if 'proveedor' in row.keys() and row['proveedor'] else 'N/A'
                cod_raw = str(row['codigo_proveedor']) if 'codigo_proveedor' in row.keys() and row['codigo_proveedor'] else ''
                desc_raw = str(row['descripcion']) if 'descripcion' in row.keys() and row['descripcion'] else ''

                prod_data = {
                    'sku_interno': sku,
                    'descripcion': str(desc_raw),
                    'marca': str(row['marca']) if 'marca' in row.keys() else '',
                    'costo_neto': float(row['costo_neto']) if 'costo_neto' in row.keys() and row['costo_neto'] else 0.0,
                    'proveedor': prov,
                    'codigo_proveedor': str(cod_raw)
                }

                self.index_product(prod_data, sku, cod_raw, desc_raw)

            conn.close()
            self.update_master_banner(detected_cols=detected_cols)
        except Exception as e:
            self.update_master_banner(f"Error conectando a DB Maestro: {e}", is_error=True)

    def letter_to_index(self, letter):
        """Convert column letter (A, B, C...) to 0-based index."""
        letter = str(letter).upper().strip()
        if letter.isdigit():
            return int(letter)
        result = 0
        for char in letter:
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1

    def load_excel(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx *.xls")])
        if not file_path: return

        self.current_file = file_path
        self.current_file_type = 'excel'
        self.lbl_file_info.configure(text=f"Cargado: {os.path.basename(file_path)}")

        try:
            xl = pd.ExcelFile(file_path)
            self.excel_data = {}

            # Clear previous sheets
            for widget in self.sheets_frame.winfo_children():
                widget.destroy()
            self.sheet_vars.clear()

            for sheet in xl.sheet_names:
                df = pd.read_excel(xl, sheet_name=sheet, header=None)
                df = df.dropna(how='all')
                self.excel_data[sheet] = df

                var = tk.BooleanVar(value=True)
                chk = ctk.CTkCheckBox(self.sheets_frame, text=sheet, variable=var)
                chk.pack(side="top", anchor="w", padx=10, pady=2)
                self.sheet_vars[sheet] = var

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el Excel: {e}")

    def load_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file_path: return

        self.current_file = file_path
        self.current_file_type = 'pdf'
        self.lbl_file_info.configure(text=f"Cargado: {os.path.basename(file_path)}")

        try:
            # Clear previous sheets UI
            for widget in self.sheets_frame.winfo_children():
                widget.destroy()
            self.sheet_vars.clear()

            # Simple preview message for PDF
            var = tk.BooleanVar(value=True)
            chk = ctk.CTkCheckBox(self.sheets_frame, text="Procesar Todo el PDF", variable=var)
            chk.pack(side="left", padx=10, pady=5)
            self.sheet_vars["PDF_ALL"] = var


        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el PDF: {e}")

    def _is_empty_cell(self, val):
        if pd.isna(val) or val is None: return True
        return str(val).strip() == ""

    def _is_orphan_description(self, text, code):
        t = str(text).strip()
        if not t: return True
        if t == str(code).strip() and t != "": return True
        if len(t) < 5: return True
        # Must have at least one alphabetical word of 3 or more letters
        words = re.findall(r'[A-Za-z]{3,}', t)
        if not words: return True
        return False

    def _is_valid_price(self, val):
        if self._is_empty_cell(val): return False
        s = str(val).strip()
        if s == '$': return False

        # Rule A: Strict numeric/currency check. Reject alphanumeric combos (e.g. 15")
        if not re.match(r'^[\$\s\d.,]+$', s):
            return False

        p = self.limpiar_precio_argentino(val)

        # Anti-Box Quantity Filter: Reject integers < 100 unless explicit $ sign
        if not math.isnan(p) and p < 100.0 and p.is_integer():
            if '$' not in s:
                return False

        return not math.isnan(p) and p > 0.0

    def _extract_segments_from_row(self, row_values):
        # Step B: Divide by empty columns
        segments = []
        current_segment = []
        consecutive_empty = 0

        for val in row_values:
            if self._is_empty_cell(val):
                consecutive_empty += 1
                if consecutive_empty >= 1 and current_segment:
                    segments.append(current_segment)
                    current_segment = []
            else:
                consecutive_empty = 0
                current_segment.append(val)

        if current_segment:
            segments.append(current_segment)

        return segments

    def _process_heuristic_row(self, row_values, context_seccion, proveedor, origen):
        # Check if entire row is empty
        if all(self._is_empty_cell(v) for v in row_values):
            return context_seccion, []

        # Header/Structure breaker: if we see "CODIGO", "PRECIO", etc. we don't clear context entirely,
        # but we definitely don't parse it as a product or title.
        junk_keywords = ["un x caj", "u x bulto", "codigo", "código", "descripcion", "precio", "lista", "linea ", "rubro", "item", "art"]

        segments = self._extract_segments_from_row(row_values)
        extracted = []
        junk_keywords = ["un x caj", "u x bulto", "codigo", "código", "descripcion", "precio", "lista", "linea ", "rubro", "item", "art"]

        # Step A: Context Title
        # Evaluamos por segmento (Isla) en lugar de toda la fila para poder leer "Títulos Side-by-Side"
        if len(segments) > 0:
            all_segments_are_titles = True
            potential_titles = []

            for seg in segments:
                non_empty = [v for v in seg if not self._is_empty_cell(v)]
                if len(non_empty) == 1:
                    val = str(non_empty[0]).strip()
                    val_lower = val.lower()
                    # Ignorar si parece un encabezado de tabla
                    if any(kw in val_lower for kw in ["codigo", "código", "precio", "descrip"]):
                        all_segments_are_titles = False
                        break
                    if not self._is_valid_price(val):
                        # Strict Anti-Letterhead Filter
                        if PATRON_MEMBRETE.search(val):
                            # Membrete detectado, no consideramos este segmento como título válido
                            potential_titles.append(None)
                        else:
                            potential_titles.append(val)
                    else:
                        all_segments_are_titles = False
                        break
                else:
                    all_segments_are_titles = False
                    break

            if all_segments_are_titles:
                # Si todos los segmentos son textos sueltos sin precios, combinamos el primero válido al contexto
                first_valid_title = next((t for t in potential_titles if t is not None), None)
                if first_valid_title:
                    # Ignore if the string is just a date/list header
                    if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', first_valid_title):
                        return context_seccion, []

                    if context_seccion and first_valid_title not in context_seccion:
                        parts = context_seccion.split(" - ")
                        if len(parts) >= 2:
                            return f"{parts[0]} - {first_valid_title}", []
                        else:
                            return f"{context_seccion} - {first_valid_title}", []
                    return first_valid_title, []
                else:
                    return context_seccion, [] # Eran todos membretes

        for seg in segments:
            # Step C: Extract rightmost valid price & Equivalences
            price_idx = -1
            precio_final = 0.0
            mixed_equivalences = []

            # Evaluate from left to right to find the actual designated price column.
            # In some sheets (Seineca), the price is in the middle and equivalences are to the right.
            # In others, price is strictly at the right. We prioritize cells with explicit $.
            explicit_price_idx = -1
            for i in range(len(seg)-1, -1, -1):
                cell_str = str(seg[i]).strip()
                # Support mixed cells like "WK6002\n$4.434"
                if '$' in cell_str:
                    lines = cell_str.split('\n')
                    price_line = next((l for l in lines if '$' in l), None)
                    if price_line and self._is_valid_price(price_line):
                        explicit_price_idx = i
                        precio_final = self.limpiar_precio_argentino(price_line)
                        mixed_equivalences.extend([l.strip() for l in lines if '$' not in l and l.strip()])
                        break
                elif self._is_valid_price(seg[i]):
                    if price_idx == -1: # Keep the rightmost fallback if no explicit $ found yet
                        price_idx = i
                        precio_final = self.limpiar_precio_argentino(seg[i])

            if explicit_price_idx != -1:
                price_idx = explicit_price_idx

            if price_idx == -1: continue # No price in segment

            # Extract Equivalences (columns to the right of the price)
            equivalences = mixed_equivalences.copy()
            for x in seg[price_idx+1:]:
                if not self._is_empty_cell(x) and not self._is_valid_price(x):
                    # Ignore pure measures like 205, 175 if it's right of the price (like battery dimensions)
                    if str(x).strip().isdigit() and len(str(x).strip()) <= 3: continue
                    equivalences.append(str(x).strip())

            # Purge Intermediate Prices (Decimals / Moneda)
            # Remove any float or currency formatted values to the left of the final price
            purged_seg = []
            for cell in seg[:price_idx]:
                if self._is_empty_cell(cell) or str(cell).strip() == '$': continue

                cell_str = str(cell).strip()
                # Purge if it's explicitly a float type, or a string containing '$', or a string with decimals
                if isinstance(cell, float):
                    continue
                if '$' in cell_str:
                    continue
                # If it matches numeric but has a decimal point/comma separating cents, purge it
                if re.match(r'^\d+[.,]\d{1,2}$', cell_str) or re.match(r'^\d{1,3}([.,]\d{3})+[.,]\d{1,2}$', cell_str):
                    continue
                # Filter out pure battery box measures (like 205, 175, 190) from being appended as text
                if cell_str.isdigit() and len(cell_str) <= 3 and int(cell_str) >= 100:
                    continue

                purged_seg.append(cell)

            # Rule B: Ignore Box Quantities in Text
            raw_text_cells = [str(x).strip() for x in purged_seg]
            text_cells = []

            for t in raw_text_cells:
                t_lower = t.lower()
                if t_lower == "un x caj" or t_lower == "u x bulto": continue
                # Discard if it's just a short integer (box quantity)
                if t.isdigit() and len(t) <= 3 and int(t) < 100: continue
                text_cells.append(t)

            if not text_cells and not equivalences: continue

            # Battery special fallback if text_cells is empty but we have equivalences
            if not text_cells and equivalences:
                text_cells = [equivalences.pop(0)]

            codigo = ""
            desc = ""

            # Identify if all text cells are purely measurements/numbers
            all_measures = all(not re.findall(r'[A-Za-z]{3,}', t) for t in text_cells)

            # Rule C: Code vs Description Split
            if all_measures:
                # E.g. ["175/70-13", "175/65-14..."]
                codigo = text_cells[0]
                # Join everything as description, don't drop the first cell if it's all measures
                # Including preserving row specific measurements like "8- 16"
                desc = " / ".join(text_cells)
            elif len(text_cells) >= 2:
                codigo = text_cells[0]
                desc = " - ".join(text_cells[1:]) # Join all subsequent cells preserving specific row measures
            elif len(text_cells) == 1:
                desc = text_cells[0]
                # Check for leading numbers as code (like "300010 Trabasil")
                match_leading = re.search(r'^(\d{4,})\s+', desc)
                if match_leading:
                    codigo = match_leading.group(1)
                else:
                    # Extract trailing numbers as code
                    match_trailing = re.search(r'\b(\d{4,})$', desc)
                    if match_trailing:
                        codigo = match_trailing.group(1)
                    else:
                        codigo = re.sub(r'[^A-Z0-9]', '', desc.upper())[:20]

            # Prevent Code Duplication in Description
            if codigo and desc:
                # Clean up if code was artificially joined inside purely measurements list (like / 30- 45)
                # If desc starts with '/ ', remove it
                desc = re.sub(r'^/\s*', '', desc)

                # Si la descripción empieza exactamente con el código, lo removemos
                pattern = f"^\\s*{re.escape(codigo)}[\\s/\\-]*"
                desc = re.sub(pattern, "", desc, flags=re.IGNORECASE).strip()

            # If description becomes empty after stripping code, fallback to context or code
            if not desc:
                desc = context_seccion if context_seccion else codigo

            cod_lower = codigo.lower()
            desc_lower = desc.lower()
            if any(kw in cod_lower for kw in junk_keywords) or any(kw in desc_lower for kw in junk_keywords):
                continue

            # Context Inheritance
            clean_sheet_name = origen.split(" (")[0] if isinstance(origen, str) else str(origen)
            generic_sheets = ["hoja1", "hoja 1", "sheet1", "sheet 1", "lista", "precios", "pag ", "pág "]
            is_generic_sheet = any(g in clean_sheet_name.lower() for g in generic_sheets)

            if self._is_orphan_description(desc, codigo):
                prefix_parts = []
                if not is_generic_sheet: prefix_parts.append(clean_sheet_name)
                if context_seccion: prefix_parts.append(context_seccion)

                if prefix_parts:
                    desc = f"{' - '.join(prefix_parts)} - {desc}"

            # Append equivalences at the end of the description if any exist
            if equivalences:
                eq_str = " / ".join(equivalences)
                desc = f"{desc} [Eq: {eq_str}]"

            marca = "GENERICA"
            if not is_generic_sheet:
                marca = clean_sheet_name.upper()
            else:
                marca = proveedor.upper()

            extracted.append({
                'proveedor': proveedor,
                'codigo_proveedor': codigo,
                'descripcion': desc,
                'marca': marca,
                'costo_neto': precio_final,
                'origen': origen
            })

        return context_seccion, extracted

    def _log_error(self, message):
        log_path = os.path.join(self.app_dir, 'error_log.txt')
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now()}] {message}\n")
        except Exception as e:
            print(f"No se pudo escribir en log: {e}")

    def _analyze_sheet_structure_with_llm(self, df_sample_str, sheet_name):
        if not genai or not self.api_key:
            return None

        import time
        client = genai.Client(api_key=self.api_key)

        prompt = f"""
Eres un analizador de estructuras de listas de precios.
Analiza la siguiente grilla de datos que representa una hoja de Excel/PDF.
Ignora explícitamente membretes, direcciones (Av. Sarmiento...), teléfonos (Tel: 0260...) y fechas (Vigencia: ...).

Devuelve una lista de bloques de tabla (TableBlock). Por cada bloque indica:
- titulo_categoria: El nombre real del rubro que encabeza ese bloque (e.g. "ABRAZADERAS PERFECTO - Standard Fleje 9mm").
- fila_inicio: Índice 0-based de la fila donde empiezan los datos de productos de este bloque.
- col_codigo: Índice 0-based de la columna del código de proveedor (null si no tiene).
- cols_descripcion: Lista de índices 0-based de columnas que forman el nombre o medida.
- col_precio_final: Índice 0-based numérico de la ÚLTIMA columna de precio (Precio Final), ignorando precios intermedios o unidades por bulto.
- requiere_prefijo_titulo: true si las celdas de descripción de ese bloque solo contienen medidas, talles o aplicaciones cortas (ej. "8- 16", '14"').

Toda la grilla usa índices base-0 exactos: F{{fila}}_C{{columna}}.

MUESTRA GRILLA (Pestaña: {sheet_name}):
{df_sample_str}
"""
        class TableBlock(BaseModel):
            titulo_categoria: str = Field(description="Título real de la categoría/producto")
            fila_inicio: int = Field(description="Índice de fila de inicio de datos")
            col_codigo: Optional[int] = Field(description="Índice de columna de código")
            cols_descripcion: List[int] = Field(description="Índices de columnas de descripción/medida")
            col_precio_final: int = Field(description="Índice de columna del precio final")
            requiere_prefijo_titulo: bool = Field(description="True si la descripción son solo medidas cortas")

        class SheetStructure(BaseModel):
            bloques: List[TableBlock]

        retries = 3
        for attempt in range(retries):
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config={'response_mime_type': 'application/json', 'response_schema': SheetStructure}
                )

                text = response.text
                text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
                text = re.sub(r'```\s*$', '', text)

                return json.loads(text.strip())

            except Exception as e:
                err_msg = str(e)
                self._log_error(f"Error LLM attempt {attempt+1}: {err_msg}")
                if "429" in err_msg or "ResourceExhausted" in err_msg:
                    time.sleep(2 * (attempt + 1)) # Backoff
                else:
                    break
        return None

    def _extract_data_from_blocks(self, df, bloques, proveedor, origen):
        # Sort blocks by start row to determine ends safely
        bloques = sorted(bloques, key=lambda x: x.get('fila_inicio', 0))

        for idx_b, block in enumerate(bloques):
            start = block.get('fila_inicio', 0)
            # If not the last block, the end is just before the next block starts
            end = bloques[idx_b+1].get('fila_inicio', len(df)) - 1 if idx_b + 1 < len(bloques) else len(df) - 1

            titulo = block.get('titulo_categoria', '')
            col_cod = block.get('col_codigo')
            cols_desc = block.get('cols_descripcion', [])
            col_precio = block.get('col_precio_final')
            req_prefijo = block.get('requiere_prefijo_titulo', False)

            if col_precio is None or not cols_desc:
                continue

            last_valid_desc = ""

            for idx in range(start, min(end + 1, len(df))):
                try:
                    row = df.iloc[idx]

                    # Extract Price (with neighbor checking fallback)
                    precio = math.nan
                    precio_raw = None
                    col_precio_real = col_precio

                    if col_precio < len(row):
                        precio_raw = row.iloc[col_precio]
                        precio = self.limpiar_precio_argentino(precio_raw)

                    # Neighbor checking if main price is invalid (compensates for LLM 1-based indexing hallucination)
                    if math.isnan(precio) or precio <= 0.01:
                        # Check left neighbor
                        if col_precio - 1 >= 0 and col_precio - 1 < len(row):
                            p_test = self.limpiar_precio_argentino(row.iloc[col_precio - 1])
                            if not math.isnan(p_test) and p_test > 0.01:
                                precio = p_test
                                precio_raw = row.iloc[col_precio - 1]
                                col_precio_real = col_precio - 1
                        # Check right neighbor if still invalid
                        if (math.isnan(precio) or precio <= 0.01) and col_precio + 1 < len(row):
                            p_test = self.limpiar_precio_argentino(row.iloc[col_precio + 1])
                            if not math.isnan(p_test) and p_test > 0.01:
                                precio = p_test
                                precio_raw = row.iloc[col_precio + 1]
                                col_precio_real = col_precio + 1

                    if math.isnan(precio) or precio <= 0.01: continue

                    # Extract Code
                    codigo = ""
                    if col_cod is not None and col_cod < len(row):
                        cod_val = row.iloc[col_cod]
                        if not pd.isna(cod_val) and str(cod_val).strip():
                            codigo = str(cod_val).strip()

                    # Extract Description
                    desc_parts = []
                    for c_idx in cols_desc:
                        if c_idx < len(row):
                            d_val = row.iloc[c_idx]
                            if not pd.isna(d_val) and str(d_val).strip():
                                # Prevent including the price column itself in the description
                                if c_idx != col_precio_real:
                                    desc_parts.append(str(d_val).strip())

                    desc = " - ".join(desc_parts)

                    # Prevent Code Duplication in Description
                    if codigo and desc:
                        pattern = f"^\\s*{re.escape(codigo)}[\\s/\\-]*"
                        desc = re.sub(pattern, "", desc, flags=re.IGNORECASE).strip()

                    # Missing description but has code (lubricants 20L case)
                    if not desc and last_valid_desc:
                        desc = last_valid_desc
                    elif desc:
                        last_valid_desc = desc

                    if not desc: continue

                    if req_prefijo and titulo:
                        desc = f"{titulo} - {desc}"
                    elif titulo and not any(w in desc.upper() for w in re.findall(r'[A-Za-z]+', titulo.upper())):
                        desc = f"{titulo} - {desc}"

                    # Synthetic Code if missing
                    if not codigo:
                        match_trailing = re.search(r'\b(\d{4,})$', desc)
                        if match_trailing:
                            codigo = match_trailing.group(1)
                        else:
                            codigo = re.sub(r'[^A-Z0-9]', '', desc.upper())[:20]

                    # Context / Brand inheritance
                    clean_sheet_name = origen.split(" (")[0] if isinstance(origen, str) else str(origen)
                    generic_sheets = ["hoja1", "hoja 1", "sheet1", "sheet 1", "lista", "precios", "pag ", "pág "]
                    is_generic_sheet = any(g in clean_sheet_name.lower() for g in generic_sheets)

                    marca = "GENERICA"
                    if not is_generic_sheet:
                        marca = clean_sheet_name.upper()
                    else:
                        marca = proveedor.upper()

                    self.extracted_data.append({
                        'proveedor': proveedor,
                        'codigo_proveedor': codigo,
                        'descripcion': desc,
                        'marca': marca,
                        'costo_neto': precio,
                        'origen': origen
                    })
                except Exception as e:
                    print(f"Extraction error row {idx}: {e}")

    def _fallback_heuristic_parse(self, df, origen, proveedor):
        context_seccion = ""
        items_extracted = 0
        for idx, row in df.iterrows():
            context_seccion, items = self._process_heuristic_row(row.values, context_seccion, proveedor, origen)
            if items:
                self.extracted_data.extend(items)
                items_extracted += len(items)
        return items_extracted

    def process_file(self):
        if not self.current_file:
            messagebox.showwarning("Aviso", "No hay archivo cargado.")
            return

        proveedor = self.entry_proveedor.get().strip().upper()
        if not proveedor:
            messagebox.showwarning("Aviso", "El campo Proveedor es obligatorio.")
            return

        if not self.api_key:
            messagebox.showwarning("Aviso", "Configura la API Key de Gemini primero.")
            return

        self.extracted_data.clear()

        # Updating UI to show progress
        if hasattr(self, 'btn_process_file'):
            original_text = self.btn_process_file.cget("text")
            self.btn_process_file.configure(text="Procesando...", state="disabled")
            self.update()

        try:
            if self.current_file_type == 'excel':
                for sheet, var in self.sheet_vars.items():
                    if not var.get(): continue
                    df = self.excel_data[sheet]

                    if hasattr(self, 'btn_process_file'):
                        self.btn_process_file.configure(text=f"Analizando pestaña: {sheet}")
                        self.update()

                    # Format to string representation using explicit 0-based F_C coords
                    sample_df_str = ""
                    count_rows = 0
                    for idx, row in df.iterrows():
                        if not all(pd.isna(x) or str(x).strip() == "" for x in row):
                            row_vals = [f"F{idx}_C{i}: {x}" for i, x in enumerate(row) if not pd.isna(x) and str(x).strip() != ""]
                            if row_vals:
                                sample_df_str += " | ".join(row_vals) + "\n"
                                count_rows += 1
                        if count_rows >= 100: break

                    if not sample_df_str.strip(): continue

                    initial_count = len(self.extracted_data)
                    # LLM request
                    structure = self._analyze_sheet_structure_with_llm(sample_df_str, sheet)
                    if structure and 'bloques' in structure:
                        self._extract_data_from_blocks(df, structure['bloques'], proveedor, sheet)

                    # FALLBACK if LLM fails to extract any valid products
                    if len(self.extracted_data) == initial_count:
                        self._log_error(f"Fallback activado en pestaña '{sheet}': IA devolvió 0 productos válidos.")
                        self._fallback_heuristic_parse(df, sheet, proveedor)

                messagebox.showinfo("Proceso Terminado", f"Se extrajeron {len(self.extracted_data)} productos válidos de Excel.")
                self.populate_audit_tables()

            elif self.current_file_type == 'pdf':
                extracted_list = extraer_productos_de_pdf(self.current_file, proveedor, self.api_key)
                if extracted_list:
                    self.extracted_data.extend(extracted_list)
                    messagebox.showinfo("Proceso Terminado", f"Se extrajeron {len(extracted_list)} productos válidos de PDF.")
                self.populate_audit_tables()

        except Exception as e:
            import traceback
            err_str = traceback.format_exc()
            self._log_error(err_str)
            messagebox.showerror("Error de Extracción", f"Ocurrió un error inesperado en PDF:\n{e}\n\nRevisa el archivo error_log.txt")

        finally:
            if hasattr(self, 'btn_process_file'):
                self.btn_process_file.configure(text=original_text, state="normal")
                self.update()

    def limpiar_descripcion_final(self, desc: str, cod_prov: str) -> str:
        if not desc:
            return ""
        desc = str(desc).strip()
        # Remove repeated provider code prefix
        if cod_prov:
            patron_cod = re.compile(r'^' + re.escape(str(cod_prov).strip()) + r'[\s\-:/]+', re.IGNORECASE)
            desc = patron_cod.sub('', desc).strip()
        # Collapse multiple spaces
        desc = re.sub(r'\s{2,}', ' ', desc)
        return desc

    def _is_semantic_match(self, desc1: str, desc2: str) -> bool:
        if not desc1 or not desc2: return False

        d1_up = str(desc1).upper()
        d2_up = str(desc2).upper()

        # Tokenize words >= 4 characters
        tokens1 = set(re.findall(r'\b[A-Za-z0-9]{4,}\b', d1_up))
        tokens2 = set(re.findall(r'\b[A-Za-z0-9]{4,}\b', d2_up))

        # Direct token intersection check
        if tokens1 and tokens2 and tokens1.intersection(tokens2):
            return True

        # Sequence matcher fallback for general similarity
        ratio = SequenceMatcher(None, d1_up, d2_up).ratio()
        return ratio >= 0.45

    def _is_prefix_match(self, proveedor_excel: str, marca_excel: str, sku_db: str) -> bool:
        if not sku_db: return False
        sku_prefix = str(sku_db).split('-')[0].upper()

        # If it's a known generic/unrelated prefix, and the incoming is explicitly from a different brand/provider
        # e.g., GEN-, MAN- vs WALKER (WAL)
        prov = str(proveedor_excel).upper()
        marca = str(marca_excel).upper()

        # Heuristic mapping for prefix rejection
        # If incoming is highly specific (WALKER -> WAL), but SKU is MAN- or GEN-
        # This acts as a strict guard.

        # If sku_prefix matches the first 3 letters of provider or brand, it's a safe match
        if prov[:3] == sku_prefix or marca[:3] == sku_prefix:
            return True

        # If SKU prefix is something completely unrelated to the incoming data (like MAN or GEN when expecting WAL)
        # This will be used in combination with semantic match, so returning False forces the semantic check to pass.
        return False

    def limpiar_precio_argentino(self, valor_crudo):
        if pd.isna(valor_crudo): return math.nan

        if not isinstance(valor_crudo, str):
            try:
                val = float(valor_crudo)
                if math.isnan(val): return math.nan
                return val
            except (ValueError, TypeError):
                return math.nan

        # Rule: If cell has a $ sign, only keep what's AFTER the last $ sign to prevent
        # adjacent columns (like a box quantity 3) from sticking to the price ($ 9.025,70 -> 39.025,70)
        s = str(valor_crudo).strip()
        if '$' in s:
            s = s.split('$')[-1]

        s = re.sub(r'[^\d.,]', '', s.strip())
        if not s:
            return math.nan

        if '.' in s and ',' in s:
            if s.rfind(',') > s.rfind('.'):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif ',' in s:
            s = s.replace(',', '.')
        elif '.' in s:
            partes = s.split('.')
            if len(partes) > 1 and len(partes[-1]) == 3:
                s = s.replace('.', '')

        try:
            val = round(float(s), 2)
            if math.isnan(val): return math.nan
            return val
        except ValueError:
            return math.nan

    def populate_audit_tables(self):
        # Clear previous tables
        for item in self.tree_updates.get_children():
            self.tree_updates.delete(item)
        for item in self.tree_new.get_children():
            self.tree_new.delete(item)

        self.audit_updates_list.clear()
        self.audit_new_list.clear()

        # Deduplicate incoming data by keeping latest cost
        dedup_extracted = {}
        for item in self.extracted_data:
            key = f"{item['proveedor']}_{item['codigo_proveedor']}_{item['descripcion']}"
            dedup_extracted[key] = item

        for key, incoming in dedup_extracted.items():
            cod_raw = str(incoming['codigo_proveedor']).strip()
            desc_raw = str(incoming['descripcion']).strip()

            cod_norm = cod_raw.upper().replace(" ", "") if cod_raw else ""
            desc_norm = re.sub(r'\s+', ' ', desc_raw.upper()) if desc_raw else ""

            existing = None

            def validate_match(candidate):
                if not candidate: return False
                # Must pass semantic check OR prefix check
                # If code is short (<= 4 chars), enforce strict semantic check regardless of prefix
                cod_len = len(cod_raw)

                is_semantic = self._is_semantic_match(incoming['descripcion'], candidate['descripcion'])
                is_prefix = self._is_prefix_match(incoming['proveedor'], incoming['marca'], candidate['sku_interno'])

                if cod_len <= 4:
                    return is_semantic

                if is_semantic or is_prefix:
                    return True

                return False

            # 1. Match by Codigo Proveedor
            if cod_norm and cod_norm in self.mapa_por_cod_prov:
                candidate = self.mapa_por_cod_prov[cod_norm]
                if validate_match(candidate):
                    existing = candidate

            # 2. Match by SKU Suffix (if not found by code)
            if not existing and cod_norm and cod_norm in self.mapa_por_sku_sufijo:
                candidate = self.mapa_por_sku_sufijo[cod_norm]
                if validate_match(candidate):
                    existing = candidate

            # 3. Match by Exact Description (Ultimate Fallback)
            if not existing and desc_norm and desc_norm in self.mapa_por_descripcion:
                existing = self.mapa_por_descripcion[desc_norm]

            if existing:
                # Existing product
                costo_ant = existing['costo_neto'] or 0.0
                costo_nvo = incoming['costo_neto']

                var_pct = 0.0
                if costo_ant > 0:
                    var_pct = ((costo_nvo - costo_ant) / costo_ant) * 100

                desc_limpia = self.limpiar_descripcion_final(existing['descripcion'], existing['codigo_proveedor'])

                self.audit_updates_list.append({
                    'sku_interno': existing['sku_interno'],
                    'proveedor': existing['proveedor'],
                    'codigo_proveedor': existing['codigo_proveedor'],
                    'descripcion': desc_limpia,
                    'marca': existing['marca'], # Original brand kept
                    'costo_ant': costo_ant,
                    'costo_nvo': costo_nvo,
                    'var_pct': var_pct
                })

                # Format for display
                var_str = f"{var_pct:+.2f}%"
                self.tree_updates.insert('', 'end', values=(
                    existing['sku_interno'],
                    existing['codigo_proveedor'],
                    desc_limpia,
                    f"${costo_ant:,.2f}",
                    f"${costo_nvo:,.2f}",
                    var_str
                ))
            else:
                # New product
                desc_limpia_nvo = self.limpiar_descripcion_final(incoming['descripcion'], incoming['codigo_proveedor'])
                incoming['descripcion'] = desc_limpia_nvo

                self.audit_new_list.append(incoming)
                self.tree_new.insert('', 'end', values=(
                    incoming['proveedor'],
                    incoming['codigo_proveedor'],
                    desc_limpia_nvo,
                    incoming['marca'],
                    f"${incoming['costo_neto']:,.2f}"
                ))

        # Switch to Audit tab to show results
        self.tabview.set("2. Auditoría Pre-Guardado")

if __name__ == "__main__":
    app = App()
    app.mainloop()
import re
import math
import pdfplumber
import traceback
