import re

with open('unificador_listas/app_temp.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We need to completely rewrite the GUI inside App class.
# Here is the general structure we want.

new_gui_code = """
    def __init__(self):
        super().__init__()
        self.title("Unificador de Listas - Barter Plus")
        self.geometry("1100x750")

        # Internal State
        self.api_key = ""
        self.master_db_path = None
        self.master_lookup = set()
        self.mapa_por_cod_prov = {}
        self.mapa_por_sku_sufijo = {}
        self.mapa_por_descripcion = {}
        self.last_master_table_name = None

        self.current_file = None
        self.current_file_type = None
        self.excel_data = {}
        self.sheet_vars = {}
        self.extracted_data = []

        self.audit_updates_list = []
        self.audit_new_list = []
        self.current_view_mode = "updates" # or "new"

        self.load_config()

        # UI Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # The treeview area

        self.setup_header()
        self.setup_control_bar()
        self.setup_dynamic_panel()
        self.setup_unified_audit_view()

        # Connect to default DB quietly
        self.auto_connect_master_db()

    def setup_header(self):
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        self.header_frame.grid_columnconfigure(1, weight=1)

        lbl_title = ctk.CTkLabel(self.header_frame, text="Barter Plus — Unificador de Listas", font=("Roboto", 20, "bold"))
        lbl_title.grid(row=0, column=0, sticky="w")

        # Center Banner
        self.lbl_master_status = ctk.CTkLabel(self.header_frame, text="🔴 Sin Conexión", text_color="#ffcc00", font=("Roboto", 13))
        self.lbl_master_status.grid(row=0, column=1, sticky="e", padx=10)

        btn_change_db = ctk.CTkButton(self.header_frame, text="Cambiar Base", width=100, height=28, command=self.link_master_db)
        btn_change_db.grid(row=0, column=2, sticky="e", padx=5)

        btn_api_key = ctk.CTkButton(self.header_frame, text="🔑 Configurar API Key", width=140, height=28, fg_color="#333333", hover_color="#555555", command=self.prompt_api_key)
        btn_api_key.grid(row=0, column=3, sticky="e")

    def prompt_api_key(self):
        dialog = ctk.CTkInputDialog(text="Pega tu Gemini API Key:", title="Configurar API Key")
        key = dialog.get_input()
        if key:
            self.api_key = key.strip()
            self.save_config()
            messagebox.showinfo("API Key", "API Key guardada correctamente.")

    def setup_control_bar(self):
        self.control_frame = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=8)
        self.control_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=5)
        self.control_frame.grid_columnconfigure(3, weight=1)

        # Proveedor
        lbl_prov = ctk.CTkLabel(self.control_frame, text="Proveedor:", font=("Roboto", 13, "bold"))
        lbl_prov.grid(row=0, column=0, padx=(15, 5), pady=15, sticky="w")

        self.entry_proveedor = ctk.CTkEntry(self.control_frame, width=200, placeholder_text="Ej: Seineca, La Casa de las Baterías...")
        self.entry_proveedor.grid(row=0, column=1, padx=5, pady=15, sticky="w")

        # File Loader
        self.btn_load_file = ctk.CTkButton(self.control_frame, text="📂 Cargar Lista (Excel / PDF)", width=180, height=35, command=self.load_file)
        self.btn_load_file.grid(row=0, column=2, padx=15, pady=15, sticky="w")

        # Analyze Button
        self.btn_process_file = ctk.CTkButton(self.control_frame, text="⚡ Analizar y Extraer Lista", font=("Roboto", 14, "bold"), fg_color="#28a745", hover_color="#218838", width=220, height=35, command=self.process_file)
        self.btn_process_file.grid(row=0, column=3, padx=15, pady=15, sticky="e")

    def setup_dynamic_panel(self):
        self.dynamic_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dynamic_frame.grid(row=2, column=0, sticky="new", padx=15, pady=5)
        # This will hold either a PDF notice or Excel sheet selectors
        self.lbl_pdf_notice = ctk.CTkLabel(self.dynamic_frame, text="📄 Archivo PDF listo para procesar.", text_color="#17a2b8", font=("Roboto", 14, "italic"))
        self.sheets_container = ctk.CTkScrollableFrame(self.dynamic_frame, height=50, fg_color="#333333", orientation="horizontal")

    def setup_unified_audit_view(self):
        self.audit_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=8)
        self.audit_frame.grid(row=3, column=0, sticky="nsew", padx=15, pady=(5, 15))
        self.grid_rowconfigure(3, weight=1)
        self.audit_frame.grid_columnconfigure(0, weight=1)
        self.audit_frame.grid_rowconfigure(1, weight=1)

        # Top Bar of Audit
        top_audit = ctk.CTkFrame(self.audit_frame, fg_color="transparent")
        top_audit.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_audit.grid_columnconfigure(3, weight=1)

        self.btn_view_updates = ctk.CTkButton(top_audit, text="🔄 Actualizaciones (0)", width=150, fg_color="#0056b3", command=lambda: self.switch_view("updates"))
        self.btn_view_updates.grid(row=0, column=0, padx=(0, 10))

        self.btn_view_new = ctk.CTkButton(top_audit, text="✨ Productos Nuevos (0)", width=150, fg_color="#444444", command=lambda: self.switch_view("new"))
        self.btn_view_new.grid(row=0, column=1)

        self.entry_search = ctk.CTkEntry(top_audit, placeholder_text="🔍 Filtrar por código, marca o descripción...", width=300)
        self.entry_search.grid(row=0, column=3, sticky="e")
        self.entry_search.bind("<KeyRelease>", self.filter_treeview)

        # Treeview
        columns = ("sku", "prov", "cod", "desc", "marca", "costo_ant", "costo_nvo", "var")
        self.tree = ttk.Treeview(self.audit_frame, columns=columns, show="headings", height=15)

        self.tree.heading("sku", text="SKU")
        self.tree.heading("prov", text="Proveedor")
        self.tree.heading("cod", text="Cód. Prov.")
        self.tree.heading("desc", text="Descripción")
        self.tree.heading("marca", text="Marca")
        self.tree.heading("costo_ant", text="Costo Ant.")
        self.tree.heading("costo_nvo", text="Costo Nvo.")
        self.tree.heading("var", text="% Var")

        self.tree.column("sku", width=100)
        self.tree.column("prov", width=80)
        self.tree.column("cod", width=100)
        self.tree.column("desc", width=300)
        self.tree.column("marca", width=100)
        self.tree.column("costo_ant", width=80, anchor="e")
        self.tree.column("costo_nvo", width=80, anchor="e")
        self.tree.column("var", width=60, anchor="e")

        # Treeview style
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", rowheight=25, fieldbackground="#2b2b2b", bordercolor="#343638", borderwidth=0)
        style.map('Treeview', background=[('selected', '#22559b')])
        style.configure("Treeview.Heading", background="#1f1f1f", foreground="white", relief="flat")
        style.map("Treeview.Heading", background=[('active', '#343638')])

        scrollbar = ttk.Scrollbar(self.audit_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)

        self.tree.grid(row=1, column=0, sticky="nsew", padx=(10, 0))
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 10))

        # Footer
        footer = ctk.CTkFrame(self.audit_frame, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        footer.grid_columnconfigure(0, weight=1)

        self.lbl_summary = ctk.CTkLabel(footer, text="Total extraído: 0 productos | 0 para actualizar | 0 nuevos", font=("Roboto", 12))
        self.lbl_summary.grid(row=0, column=0, sticky="w")

        self.btn_export = ctk.CTkButton(footer, text="💾 Exportar Excel Unificado (.xlsx)", fg_color="#198754", hover_color="#146c43", font=("Roboto", 13, "bold"), command=self.export_excel)
        self.btn_export.grid(row=0, column=1, sticky="e")

        # Include a checkbox to include new products in export
        self.chk_var_new = tk.BooleanVar(value=True)
        self.chk_include_new = ctk.CTkCheckBox(footer, text="Incluir Nuevos", variable=self.chk_var_new)
        self.chk_include_new.grid(row=0, column=2, sticky="e", padx=(15, 0))

    def switch_view(self, mode):
        self.current_view_mode = mode
        if mode == "updates":
            self.btn_view_updates.configure(fg_color="#0056b3")
            self.btn_view_new.configure(fg_color="#444444")
            self.tree.column("costo_ant", minwidth=80, width=80, stretch=False)
            self.tree.column("var", minwidth=60, width=60, stretch=False)
            self.tree.heading("costo_nvo", text="Costo Nvo.")
        else:
            self.btn_view_updates.configure(fg_color="#444444")
            self.btn_view_new.configure(fg_color="#0056b3")
            self.tree.column("costo_ant", minwidth=0, width=0, stretch=False)
            self.tree.column("var", minwidth=0, width=0, stretch=False)
            self.tree.heading("costo_nvo", text="Costo Final")

        self.filter_treeview() # Re-render current list

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Listas de Precios", "*.xlsx *.xls *.pdf"), ("Excel", "*.xlsx *.xls"), ("PDF", "*.pdf")])
        if not file_path: return

        self.current_file = file_path
        filename = os.path.basename(file_path)

        # Auto-fill provider if empty
        if not self.entry_proveedor.get().strip():
            # Basic cleanup of filename for provider name
            prov_name = re.sub(r'\\.(pdf|xlsx|xls)$', '', filename, flags=re.IGNORECASE)
            prov_name = re.sub(r'[-_\\d]+', ' ', prov_name).strip().upper()
            if len(prov_name) > 15:
                prov_name = prov_name[:15]
            self.entry_proveedor.insert(0, prov_name)

        if filename.lower().endswith('.pdf'):
            self.current_file_type = 'pdf'

            # Update dynamic panel
            self.sheets_container.grid_forget()
            self.lbl_pdf_notice.configure(text=f"📄 Archivo PDF listo para procesar: {filename}")
            self.lbl_pdf_notice.pack(side="left", padx=10, pady=5)

            import PyPDF2
            try:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    pages = len(reader.pages)
                    self.lbl_pdf_notice.configure(text=f"📄 Archivo PDF listo para procesar: {filename} ({pages} páginas)")
            except:
                pass

        else:
            self.current_file_type = 'excel'
            self.lbl_pdf_notice.pack_forget()

            try:
                xl = pd.ExcelFile(file_path)
                self.excel_data = {}

                # Clear previous sheets
                for widget in self.sheets_container.winfo_children():
                    widget.destroy()
                self.sheet_vars.clear()

                self.sheets_container.grid(row=0, column=0, sticky="ew")

                btn_toggle_all = ctk.CTkButton(self.sheets_container, text="Marcar Todas", width=100, fg_color="#555", command=self.select_all_sheets)
                btn_toggle_all.pack(side="left", padx=10)

                for sheet in xl.sheet_names:
                    df = pd.read_excel(xl, sheet_name=sheet, header=None)
                    df = df.dropna(how='all')
                    self.excel_data[sheet] = df

                    var = tk.BooleanVar(value=True)
                    chk = ctk.CTkCheckBox(self.sheets_container, text=sheet, variable=var)
                    chk.pack(side="left", padx=10, pady=5)
                    self.sheet_vars[sheet] = var

            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar el Excel: {e}")

    def filter_treeview(self, event=None):
        search_term = self.entry_search.get().strip().lower()

        for item in self.tree.get_children():
            self.tree.delete(item)

        target_list = self.audit_updates_list if self.current_view_mode == "updates" else self.audit_new_list

        for item in target_list:
            if search_term:
                search_string = f"{item.get('codigo_proveedor','')} {item.get('descripcion','')} {item.get('marca','')} {item.get('sku_interno','')} {item.get('proveedor','')}".lower()
                if search_term not in search_string:
                    continue

            if self.current_view_mode == "updates":
                self.tree.insert("", "end", values=(
                    item.get('sku_interno', ''),
                    item.get('proveedor', ''),
                    item.get('codigo_proveedor', ''),
                    item.get('descripcion', ''),
                    item.get('marca', ''),
                    f"${item.get('costo_ant', 0.0):.2f}",
                    f"${item.get('costo_nvo', 0.0):.2f}",
                    f"{item.get('variacion', 0.0):.1f}%"
                ))
            else:
                 self.tree.insert("", "end", values=(
                    "NUEVO",
                    item.get('proveedor', ''),
                    item.get('codigo_proveedor', ''),
                    item.get('descripcion', ''),
                    item.get('marca', ''),
                    "",
                    f"${item.get('costo_neto', 0.0):.2f}",
                    ""
                ))
"""

# Now we need to remove the old App.__init__ and the old setup_ methods, and insert our new ones.
# First, let's find the App class definition
app_idx = content.find("class App(ctk.CTk):")

# Find the end of `setup_export_tab` to remove all old UI logic.
end_setup_idx = content.find("def auto_connect_master_db")

if app_idx != -1 and end_setup_idx != -1:
    content = content[:app_idx + len("class App(ctk.CTk):")] + "\n" + new_gui_code + "\n" + content[end_setup_idx:]

    # We also need to remove load_pdf, load_excel, setup_import_tab, setup_audit_tab, setup_export_tab if they are still lying around.
    # They should be gone since they were between `__init__` and `auto_connect_master_db`. Let's double check.

    # Write to a temp file and test
    with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("UI rewrite applied.")
else:
    print("Could not find App class or auto_connect_master_db.")
