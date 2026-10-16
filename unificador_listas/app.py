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

# App Config
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Unificador de Listas - Barter Plus")
        self.local_db_path = "unificador_interno.db"
        self.master_db_path = None

        # Triple Index Maps
        self.mapa_por_cod_prov = {}
        self.mapa_por_sku_sufijo = {}
        self.mapa_por_descripcion = {}

        self.config_file = "config.json"

        self.init_local_db()
        self.load_config()
        self.auto_connect_master_db()

        self.geometry("1000x700")

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
            except:
                pass

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump({'master_db_path': self.master_db_path}, f)

    def setup_import_tab(self):
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

        self.btn_process_file = ctk.CTkButton(self.map_frame, text="Autodetectar y Procesar Productos", font=("Roboto", 14, "bold"), command=self.process_file, fg_color="green", height=40)
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
            if 'productos_maestro' in tables: table_name = 'productos_maestro'
            elif 'productos' in tables: table_name = 'productos'
            elif 'producto' in tables: table_name = 'producto'

            if not table_name:
                self.update_master_banner("Aviso: No se detectó tabla de productos en la DB maestra.", is_error=True)
                conn.close()
                return

            self.last_master_table_name = table_name

            c.execute(f"PRAGMA table_info({table_name})")
            cols = [r['name'].lower() for r in c.fetchall()]

            sku_col = 'sku_interno' if 'sku_interno' in cols else ('sku' if 'sku' in cols else 'codigo')
            prov_col = 'proveedor' if 'proveedor' in cols else 'proveedor_id'
            cod_col = 'codigo_proveedor' if 'codigo_proveedor' in cols else ('codigo' if 'codigo' in cols else sku_col)
            desc_col = 'descripcion' if 'descripcion' in cols else 'nombre'
            marca_col = 'marca' if 'marca' in cols else ('marca_id' if 'marca_id' in cols else "'' as marca")
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
                prov = str(row['proveedor']).strip().upper() if row['proveedor'] else 'N/A'
                cod_raw = row['codigo_proveedor']
                desc_raw = row['descripcion']

                prod_data = {
                    'sku_interno': sku,
                    'descripcion': str(desc_raw),
                    'marca': str(row['marca']),
                    'costo_neto': float(row['costo_neto']) if row['costo_neto'] else 0.0,
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

        # Step A: Context Title
        non_empty = [v for v in row_values if not self._is_empty_cell(v)]
        if len(non_empty) == 1:
            val = non_empty[0]
            if not self._is_valid_price(val):
                return str(val).strip(), []

        segments = self._extract_segments_from_row(row_values)
        extracted = []
        junk_keywords = ["un x caj", "u x bulto", "codigo", "código", "descripcion", "precio", "lista", "linea ", "rubro", "item", "art"]

        for seg in segments:
            # Step C: Extract rightmost valid price
            price_idx = -1
            precio_final = 0.0

            for i in range(len(seg)-1, -1, -1):
                if self._is_valid_price(seg[i]):
                    price_idx = i
                    precio_final = self.limpiar_precio_argentino(seg[i])
                    break

            if price_idx == -1: continue # No price in segment

            # Rule B: Ignore Box Quantities in Text
            raw_text_cells = [str(x).strip() for x in seg[:price_idx] if not self._is_empty_cell(x) and str(x).strip() != '$']
            text_cells = []

            for t in raw_text_cells:
                t_lower = t.lower()
                if t_lower == "un x caj" or t_lower == "u x bulto": continue
                # Discard if it's just a short integer (box quantity)
                if t.isdigit() and len(t) <= 3 and int(t) < 1000: continue
                text_cells.append(t)

            if not text_cells: continue

            codigo = ""
            desc = ""

            # Identify if all text cells are purely measurements/numbers
            all_measures = all(not re.findall(r'[A-Za-z]{3,}', t) for t in text_cells)

            # Rule C: Code vs Description Split
            if all_measures:
                # E.g. ["175/70-13", "175/65-14..."]
                codigo = text_cells[0]
                # Join everything as description, don't drop the first cell if it's all measures
                desc = " / ".join(text_cells)
            elif len(text_cells) >= 2:
                codigo = text_cells[0]
                desc = " ".join(text_cells[1:])
            elif len(text_cells) == 1:
                desc = text_cells[0]
                # Extract trailing numbers as code
                match = re.search(r'\b(\d{4,})$', desc)
                if match:
                    codigo = match.group(1)
                else:
                    codigo = re.sub(r'[^A-Z0-9]', '', desc.upper())[:20]

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

    def process_file(self):
        if not self.current_file:
            messagebox.showwarning("Aviso", "No hay archivo cargado.")
            return

        proveedor = self.entry_proveedor.get().strip().upper()
        if not proveedor:
            messagebox.showwarning("Aviso", "El campo Proveedor es obligatorio.")
            return

        self.extracted_data.clear()

        if self.current_file_type == 'excel':
            for sheet, var in self.sheet_vars.items():
                if not var.get(): continue
                df = self.excel_data[sheet]
                context_seccion = ""
                for idx, row in df.iterrows():
                    context_seccion, items = self._process_heuristic_row(row.values, context_seccion, proveedor, sheet)
                    self.extracted_data.extend(items)

            messagebox.showinfo("Proceso Terminado", f"Se extrajeron {len(self.extracted_data)} productos válidos de Excel.")
            self.populate_audit_tables()

        elif self.current_file_type == 'pdf':
            with pdfplumber.open(self.current_file) as pdf:
                for i, page in enumerate(pdf.pages):
                    context_seccion = ""
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                if not row: continue
                                context_seccion, items = self._process_heuristic_row(row, context_seccion, proveedor, f"Pag {i+1}")
                                self.extracted_data.extend(items)
                    else:
                        text = page.extract_text(vertical_strategy="lines")
                        if text:
                            lines = text.split('\n')
                            for line in lines:
                                parts = [p.strip() for p in line.split('  ') if p.strip()]
                                context_seccion, items = self._process_heuristic_row(parts, context_seccion, proveedor, f"Pag {i+1} (Lineas)")
                                self.extracted_data.extend(items)

            messagebox.showinfo("Proceso Terminado", f"Se extrajeron {len(self.extracted_data)} productos válidos de PDF.")
            self.populate_audit_tables()

    def limpiar_precio_argentino(self, valor_crudo):
        if pd.isna(valor_crudo): return math.nan

        if not isinstance(valor_crudo, str):
            try:
                val = float(valor_crudo)
                if math.isnan(val): return math.nan
                return val
            except (ValueError, TypeError):
                return math.nan

        s = re.sub(r'[^\d.,]', '', str(valor_crudo).strip())
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

            # 1. Match by Codigo Proveedor
            if cod_norm and cod_norm in self.mapa_por_cod_prov:
                existing = self.mapa_por_cod_prov[cod_norm]
            # 2. Match by SKU Suffix
            elif cod_norm and cod_norm in self.mapa_por_sku_sufijo:
                existing = self.mapa_por_sku_sufijo[cod_norm]
            # 3. Match by Exact Description
            elif desc_norm and desc_norm in self.mapa_por_descripcion:
                existing = self.mapa_por_descripcion[desc_norm]

            if existing:
                # Existing product
                costo_ant = existing['costo_neto'] or 0.0
                costo_nvo = incoming['costo_neto']

                var_pct = 0.0
                if costo_ant > 0:
                    var_pct = ((costo_nvo - costo_ant) / costo_ant) * 100

                self.audit_updates_list.append({
                    'sku_interno': existing['sku_interno'],
                    'proveedor': existing['proveedor'],
                    'codigo_proveedor': existing['codigo_proveedor'],
                    'descripcion': existing['descripcion'], # Original description kept
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
                    existing['descripcion'],
                    f"${costo_ant:,.2f}",
                    f"${costo_nvo:,.2f}",
                    var_str
                ))
            else:
                # New product
                self.audit_new_list.append(incoming)
                self.tree_new.insert('', 'end', values=(
                    incoming['proveedor'],
                    incoming['codigo_proveedor'],
                    incoming['descripcion'],
                    incoming['marca'],
                    f"${incoming['costo_neto']:,.2f}"
                ))

        # Switch to Audit tab to show results
        self.tabview.set("2. Auditoría Pre-Guardado")

if __name__ == "__main__":
    app = App()
    app.mainloop()
