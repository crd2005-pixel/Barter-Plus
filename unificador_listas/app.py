import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sqlite3
import pandas as pd
import pdfplumber
import os
import re
from datetime import datetime
import hashlib

# App Config
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Unificador de Listas - Barter Plus")
        self.db_path = "inventario_barter.db"
        self.master_lookup = {}

        self.init_db()
        self.load_master_index()
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

    def setup_import_tab(self):
        # Frame for file selection
        self.file_frame = ctk.CTkFrame(self.tab_import)
        self.file_frame.pack(fill="x", padx=10, pady=10)

        self.btn_load_excel = ctk.CTkButton(self.file_frame, text="Cargar Excel", command=self.load_excel)
        self.btn_load_excel.pack(side="left", padx=10, pady=10)

        self.btn_load_pdf = ctk.CTkButton(self.file_frame, text="Cargar PDF", command=self.load_pdf)
        self.btn_load_pdf.pack(side="left", padx=10, pady=10)

        self.lbl_file_info = ctk.CTkLabel(self.file_frame, text="Ningún archivo cargado")
        self.lbl_file_info.pack(side="left", padx=10, pady=10)

        self.config_frame = ctk.CTkFrame(self.tab_import)
        self.config_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Mapping inputs
        self.map_frame = ctk.CTkFrame(self.config_frame)
        self.map_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(self.map_frame, text="Proveedor (Obligatorio):").pack(side="left", padx=5)
        self.entry_proveedor = ctk.CTkEntry(self.map_frame, width=150)
        self.entry_proveedor.pack(side="left", padx=5)

        ctk.CTkLabel(self.map_frame, text="Col. Código:").pack(side="left", padx=5)
        self.entry_col_cod = ctk.CTkEntry(self.map_frame, width=50)
        self.entry_col_cod.pack(side="left", padx=5)
        self.entry_col_cod.insert(0, "A")

        ctk.CTkLabel(self.map_frame, text="Col. Desc:").pack(side="left", padx=5)
        self.entry_col_desc = ctk.CTkEntry(self.map_frame, width=50)
        self.entry_col_desc.pack(side="left", padx=5)
        self.entry_col_desc.insert(0, "B")

        ctk.CTkLabel(self.map_frame, text="Col. Marca:").pack(side="left", padx=5)
        self.entry_col_marca = ctk.CTkEntry(self.map_frame, width=50)
        self.entry_col_marca.pack(side="left", padx=5)
        self.entry_col_marca.insert(0, "C")

        ctk.CTkLabel(self.map_frame, text="Col. Precio:").pack(side="left", padx=5)
        self.entry_col_precio = ctk.CTkEntry(self.map_frame, width=50)
        self.entry_col_precio.pack(side="left", padx=5)
        self.entry_col_precio.insert(0, "D")

        self.btn_process_file = ctk.CTkButton(self.map_frame, text="Procesar Archivo", command=self.process_file, fg_color="green")
        self.btn_process_file.pack(side="right", padx=10)

        # Tabs / preview
        self.sheets_frame = ctk.CTkScrollableFrame(self.config_frame, height=100)
        self.sheets_frame.pack(fill="x", pady=5)
        self.sheet_vars = {}

        # Treeview for preview
        columns = ('Col A', 'Col B', 'Col C', 'Col D', 'Col E', 'Col F')
        self.tree_preview = ttk.Treeview(self.config_frame, columns=columns, show='headings', height=10)
        for col in columns:
            self.tree_preview.heading(col, text=col)
            self.tree_preview.column(col, width=100)
        self.tree_preview.pack(fill="both", expand=True, pady=5)

        # Temp list for processing results
        self.extracted_data = []
        self.current_file = None
        self.current_file_type = None
        self.excel_data = None # Dictionary of DataFrames

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

        self.btn_apply_db = ctk.CTkButton(self.export_frame, text="Aplicar Cambios en Base de Datos", command=self.apply_db_changes, fg_color="red")
        self.btn_apply_db.pack(pady=10)

        self.btn_export_excel = ctk.CTkButton(self.export_frame, text="Exportar Excel Unificado", command=self.export_excel, fg_color="green")
        self.btn_export_excel.pack(pady=10)

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
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updates = 0
            inserts = 0

            # Upsert Updates
            for item in self.audit_updates_list:
                c.execute('''UPDATE productos_maestro
                             SET costo_neto = ?, fecha_actualizacion = ?
                             WHERE sku_interno = ?''',
                          (item['costo_nvo'], now, item['sku_interno']))
                updates += 1

            # Insert New Products if checked
            if self.chk_var_new.get():
                for item in self.audit_new_list:
                    sku = self.generate_sku(item['proveedor'], item['codigo_proveedor'], item['marca'], item['descripcion'])

                    try:
                        c.execute('''INSERT INTO productos_maestro
                                     (sku_interno, proveedor, codigo_proveedor, descripcion, marca, costo_neto, contenido_caja, fecha_actualizacion)
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                  (sku, item['proveedor'], item['codigo_proveedor'], item['descripcion'], item['marca'], item['costo_neto'], '1', now))
                        inserts += 1
                    except sqlite3.IntegrityError:
                        # Fallback in case SKU or (proveedor, codigo_proveedor) already exists (should be caught by master index, but double check)
                        pass

            conn.commit()
            conn.close()

            messagebox.showinfo("Éxito", f"Base de datos actualizada.\nActualizados: {updates}\nNuevos (Insertados): {inserts}")

            # Reload index and clear temp memory
            self.load_master_index()
            self.extracted_data.clear()
            self.audit_updates_list.clear()
            self.audit_new_list.clear()
            for item in self.tree_updates.get_children(): self.tree_updates.delete(item)
            for item in self.tree_new.get_children(): self.tree_new.delete(item)

        except Exception as e:
            messagebox.showerror("Error DB", f"Ocurrió un error guardando en DB: {e}")

    def export_excel(self):
        try:
            conn = sqlite3.connect(self.db_path)
            query = "SELECT sku_interno, proveedor, codigo_proveedor, descripcion, marca, costo_neto, contenido_caja, fecha_actualizacion FROM productos_maestro"
            df = pd.read_sql_query(query, conn)
            conn.close()

            if df.empty:
                messagebox.showinfo("Aviso", "La base de datos está vacía, no hay nada que exportar.")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel Files", "*.xlsx")],
                initialfile="Inventario_Maestro_Unificado.xlsx"
            )

            if file_path:
                df.to_excel(file_path, index=False, engine='openpyxl')
                messagebox.showinfo("Éxito", f"Archivo exportado correctamente a:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Error de Exportación", f"No se pudo exportar a Excel: {e}")

    def init_db(self):
        # Enforcing connection to SQLite, readonly for the main app logic is a principle,
        # but here we might need to initialize tables if they don't exist yet,
        # or we assume they exist. The instruction says: "conectar al archivo SQLite de Barter Plus o importar el padron".
        # We'll ensure the table exists just in case.
        try:
            conn = sqlite3.connect(self.db_path)
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
        except Exception as e:
            messagebox.showerror("Error DB", f"Error inicializando base de datos: {e}")

    def load_master_index(self):
        try:
            # Connect in Read-Only mode for the lookup index
            uri = f"file:{os.path.abspath(self.db_path)}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute("SELECT sku_interno, proveedor, codigo_proveedor, descripcion, marca, costo_neto FROM productos_maestro")
            rows = c.fetchall()

            self.master_lookup.clear()
            for row in rows:
                prov = str(row['proveedor']).strip().upper()
                cod = str(row['codigo_proveedor']).strip().upper().replace(" ", "")

                # Composite key for strict matching
                key = (prov, cod)
                self.master_lookup[key] = {
                    'sku_interno': row['sku_interno'],
                    'descripcion': row['descripcion'],
                    'marca': row['marca'],
                    'costo_neto': row['costo_neto'],
                    'proveedor': row['proveedor'],
                    'codigo_proveedor': row['codigo_proveedor']
                }

            conn.close()
            print(f"Índice maestro cargado con {len(self.master_lookup)} registros.")
        except Exception as e:
            print(f"Advertencia: No se pudo cargar el índice (puede que la DB esté vacía): {e}")

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
                chk.pack(side="left", padx=10, pady=5)
                self.sheet_vars[sheet] = var

            # Show preview of first sheet
            if xl.sheet_names:
                self.update_preview(self.excel_data[xl.sheet_names[0]])

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el Excel: {e}")

    def update_preview(self, df):
        # Clear tree
        for item in self.tree_preview.get_children():
            self.tree_preview.delete(item)

        # Insert first 15 rows
        for i, row in df.head(15).iterrows():
            values = [str(x) if pd.notna(x) else "" for x in row.values]
            # Pad with empty if needed
            while len(values) < 6:
                values.append("")
            self.tree_preview.insert('', 'end', values=values[:6])

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

            # Extract first page table for preview
            with pdfplumber.open(file_path) as pdf:
                if len(pdf.pages) > 0:
                    page = pdf.pages[0]
                    # Simple table extraction for preview
                    table = page.extract_table()
                    if table:
                        df = pd.DataFrame(table)
                        self.update_preview(df)
                    else:
                        messagebox.showinfo("Aviso", "No se detectó tabla automática en la primera página. Se intentará extracción por líneas.")
                        # Create empty df for preview
                        self.update_preview(pd.DataFrame(columns=range(6)))

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el PDF: {e}")

    def process_file(self):
        if not self.current_file:
            messagebox.showwarning("Aviso", "No hay archivo cargado.")
            return

        proveedor = self.entry_proveedor.get().strip().upper()
        if not proveedor:
            messagebox.showwarning("Aviso", "El campo Proveedor es obligatorio.")
            return

        try:
            col_cod = self.letter_to_index(self.entry_col_cod.get())
            col_desc = self.letter_to_index(self.entry_col_desc.get())
            col_marca = self.letter_to_index(self.entry_col_marca.get())
            col_precio = self.letter_to_index(self.entry_col_precio.get())
        except Exception as e:
            messagebox.showwarning("Aviso", "Configuración de columnas inválida.")
            return

        self.extracted_data.clear() # Flush per run

        if self.current_file_type == 'excel':
            for sheet, var in self.sheet_vars.items():
                if not var.get():
                    continue
                df = self.excel_data[sheet]
                for idx, row in df.iterrows():
                    try:
                        if len(row) <= max(col_cod, col_desc, col_precio):
                            continue

                        cod = str(row.iloc[col_cod]).strip() if pd.notna(row.iloc[col_cod]) else ""
                        desc = str(row.iloc[col_desc]).strip() if pd.notna(row.iloc[col_desc]) else ""

                        # Marca can be from col or sheet name
                        if len(row) > col_marca and pd.notna(row.iloc[col_marca]):
                            marca = str(row.iloc[col_marca]).strip().upper()
                        else:
                            marca = "GENERICA"

                        precio_raw = row.iloc[col_precio]

                        # Anti-desfase: skip empty cod, repetitive headers, or invalid prices
                        if not cod or cod.lower() in ["código", "codigo", "item", "art"]:
                            continue

                        precio = self.limpiar_precio_argentino(precio_raw)
                        if precio <= 0:
                            continue

                        self.extracted_data.append({
                            'proveedor': proveedor,
                            'codigo_proveedor': cod,
                            'descripcion': desc,
                            'marca': marca,
                            'costo_neto': precio,
                            'origen': sheet
                        })
                    except Exception as e:
                        # Skip row on parsing errors
                        pass

            messagebox.showinfo("Proceso Terminado", f"Se extrajeron {len(self.extracted_data)} productos válidos de Excel.")
            self.populate_audit_tables()

        elif self.current_file_type == 'pdf':
            with pdfplumber.open(self.current_file) as pdf:
                for i, page in enumerate(pdf.pages):
                    # Try extract_table first
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                if not row: continue
                                try:
                                    if len(row) <= max(col_cod, col_desc, col_precio): continue

                                    cod = str(row[col_cod]).strip() if row[col_cod] else ""
                                    desc = str(row[col_desc]).strip() if row[col_desc] else ""

                                    if len(row) > col_marca and row[col_marca]:
                                        marca = str(row[col_marca]).strip().upper()
                                    else:
                                        marca = "GENERICA"

                                    precio_raw = row[col_precio]

                                    if not cod or cod.lower() in ["código", "codigo", "item", "art"]:
                                        continue

                                    precio = self.limpiar_precio_argentino(precio_raw)
                                    if precio <= 0: continue

                                    self.extracted_data.append({
                                        'proveedor': proveedor,
                                        'codigo_proveedor': cod,
                                        'descripcion': desc,
                                        'marca': marca,
                                        'costo_neto': precio,
                                        'origen': f"Pag {i+1}"
                                    })
                                except Exception:
                                    pass
                    else:
                        # Fallback to lines if table extraction fails completely
                        text = page.extract_text(vertical_strategy="lines")
                        if text:
                            lines = text.split('\n')
                            for line in lines:
                                parts = [p.strip() for p in line.split('  ') if p.strip()] # Double space as separator heuristic
                                try:
                                    if len(parts) <= max(col_cod, col_desc, col_precio): continue
                                    cod = str(parts[col_cod]).strip()
                                    desc = str(parts[col_desc]).strip()
                                    marca = "GENERICA"
                                    if len(parts) > col_marca:
                                        marca = str(parts[col_marca]).strip().upper()
                                    precio_raw = parts[col_precio]

                                    if not cod or cod.lower() in ["código", "codigo", "item", "art"]: continue
                                    precio = self.limpiar_precio_argentino(precio_raw)
                                    if precio <= 0: continue

                                    self.extracted_data.append({
                                        'proveedor': proveedor,
                                        'codigo_proveedor': cod,
                                        'descripcion': desc,
                                        'marca': marca,
                                        'costo_neto': precio,
                                        'origen': f"Pag {i+1} (Lineas)"
                                    })
                                except Exception:
                                    pass

            messagebox.showinfo("Proceso Terminado", f"Se extrajeron {len(self.extracted_data)} productos válidos de PDF.")
            self.populate_audit_tables()

    def limpiar_precio_argentino(self, valor_crudo):
        if not isinstance(valor_crudo, str):
            try:
                return float(valor_crudo)
            except (ValueError, TypeError):
                return 0.0

        s = re.sub(r'[^\d.,]', '', str(valor_crudo).strip())
        if not s:
            return 0.0

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
            return round(float(s), 2)
        except ValueError:
            return 0.0

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
            # Normalize for matching
            cod_norm = str(item['codigo_proveedor']).upper().replace(" ", "")
            key = (item['proveedor'], cod_norm)
            dedup_extracted[key] = item

        for key, incoming in dedup_extracted.items():
            if key in self.master_lookup:
                # Existing product
                existing = self.master_lookup[key]
                costo_ant = existing['costo_neto'] or 0.0
                costo_nvo = incoming['costo_neto']

                var_pct = 0.0
                if costo_ant > 0:
                    var_pct = ((costo_nvo - costo_ant) / costo_ant) * 100

                self.audit_updates_list.append({
                    'sku_interno': existing['sku_interno'],
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
