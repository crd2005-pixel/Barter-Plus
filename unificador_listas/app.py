import customtkinter as ctk
from tkinter import ttk
import os
import sys

# Ajuste temporal del sys.path para poder importar los módulos src estando dentro o fuera de unificador_listas
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if os.path.dirname(current_dir) not in sys.path:
    sys.path.insert(0, os.path.dirname(current_dir))

from unificador_listas.src.database import load_config, save_config, get_readonly_connection

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Barter Plus — Unificador de Listas")
        self.geometry("1000x700")

        # --- UI Design ---
        # 1. Header Superior Compacto (1 sola fila)
        self.header_frame = ctk.CTkFrame(self, height=40)
        self.header_frame.pack(fill="x", padx=10, pady=5)

        self.lbl_title = ctk.CTkLabel(self.header_frame, text="Barter Plus — Unificador de Listas", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_title.pack(side="left", padx=10)

        self.combo_precio_baterias = ctk.CTkComboBox(self.header_frame, values=["Usar Final C/Usada", "Usar Costo S/Usada"], width=150)
        self.combo_precio_baterias.pack(side="left", padx=10)

        self.lbl_db_status = ctk.CTkLabel(self.header_frame, text="🟢 Base Barter Plus (Solo Lectura)")
        self.lbl_db_status.pack(side="left", padx=10, expand=True)

        self.btn_api_key = ctk.CTkButton(self.header_frame, text="🔑 API Key", width=100, command=self.open_api_key_modal)
        self.btn_api_key.pack(side="right", padx=10)

        # 2. Panel de Carga Unificado
        self.load_frame = ctk.CTkFrame(self, height=50)
        self.load_frame.pack(fill="x", padx=10, pady=5)

        self.entry_proveedor = ctk.CTkEntry(self.load_frame, placeholder_text="Proveedor", width=200)
        self.entry_proveedor.pack(side="left", padx=10, pady=10)

        self.btn_select_file = ctk.CTkButton(self.load_frame, text="📂 Seleccionar Lista (Excel o PDF)", command=self.select_file)
        self.btn_select_file.pack(side="left", padx=10)

        self.btn_analyze = ctk.CTkButton(self.load_frame, text="⚡ Analizar y Extraer Lista", fg_color="green", hover_color="darkgreen")
        self.btn_analyze.pack(side="left", padx=10)

        self.lbl_file_status = ctk.CTkLabel(self.load_frame, text="")
        self.lbl_file_status.pack(side="left", padx=10)

        # Selector Dinámico de Pestañas (Oculto por defecto)
        self.sheet_frame = ctk.CTkFrame(self, height=40)
        self.sheet_frame.pack_forget()

        self.lbl_sheets = ctk.CTkLabel(self.sheet_frame, text="Hojas a procesar:")
        self.lbl_sheets.pack(side="left", padx=10)

        self.btn_toggle_sheets = ctk.CTkButton(self.sheet_frame, text="Marcar / Desmarcar Todas", command=self.toggle_sheets)
        self.btn_toggle_sheets.pack(side="left", padx=10)

        self.sheet_checkboxes_frame = ctk.CTkScrollableFrame(self.sheet_frame, height=40, orientation="horizontal")
        self.sheet_checkboxes_frame.pack(side="left", fill="x", expand=True, padx=10, pady=5)

        self.sheet_vars = {}

        # 3. Área Principal de Auditoría y Exportación
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Pestañas custom
        self.tab_frame = ctk.CTkFrame(self.main_frame, height=30, fg_color="transparent")
        self.tab_frame.pack(fill="x", pady=(5,0))

        self.btn_tab_updates = ctk.CTkButton(self.tab_frame, text="🔄 Actualizaciones de Precio (0)", width=250, command=lambda: self.show_tree("updates"))
        self.btn_tab_updates.pack(side="left", padx=5)

        self.btn_tab_news = ctk.CTkButton(self.tab_frame, text="✨ Productos Nuevos (0)", width=250, fg_color="gray", command=lambda: self.show_tree("news"))
        self.btn_tab_news.pack(side="left", padx=5)

        self.entry_search = ctk.CTkEntry(self.tab_frame, placeholder_text="🔍 Filtrar por código, marca o descripción...", width=300)
        self.entry_search.pack(side="right", padx=5)

        # Treeviews
        self.tree_frame = ctk.CTkFrame(self.main_frame)
        self.tree_frame.pack(fill="both", expand=True, pady=5)

        # Tree Updates
        self.tree_updates = ttk.Treeview(self.tree_frame, columns=("SKU", "Cod. Prov.", "Descripción", "Marca", "Costo Ant.", "Costo Nvo.", "Var. %"), show="headings")
        self.tree_updates.heading("SKU", text="SKU")
        self.tree_updates.heading("Cod. Prov.", text="Cod. Prov.")
        self.tree_updates.heading("Descripción", text="Descripción")
        self.tree_updates.heading("Marca", text="Marca")
        self.tree_updates.heading("Costo Ant.", text="Costo Ant.")
        self.tree_updates.heading("Costo Nvo.", text="Costo Nvo.")
        self.tree_updates.heading("Var. %", text="Var. %")
        self.tree_updates.pack(fill="both", expand=True)

        # Tree News
        self.tree_news = ttk.Treeview(self.tree_frame, columns=("Proveedor", "Cod. Prov.", "Descripción", "Marca", "Costo"), show="headings")
        self.tree_news.heading("Proveedor", text="Proveedor")
        self.tree_news.heading("Cod. Prov.", text="Cod. Prov.")
        self.tree_news.heading("Descripción", text="Descripción")
        self.tree_news.heading("Marca", text="Marca")
        self.tree_news.heading("Costo", text="Costo")
        # news hidden by default

        self.current_tree = "updates"

        # Footer
        self.footer_frame = ctk.CTkFrame(self, height=50)
        self.footer_frame.pack(fill="x", padx=10, pady=10)

        self.lbl_resume = ctk.CTkLabel(self.footer_frame, text="Total: 0")
        self.lbl_resume.pack(side="left", padx=10)

        self.btn_export = ctk.CTkButton(self.footer_frame, text="💾 Exportar Excel Unificado (.xlsx)", height=40, font=ctk.CTkFont(weight="bold"))
        self.btn_export.pack(side="right", padx=10)

        # Cargar config
        self.config = load_config()

    def open_api_key_modal(self):
        # Diálogo modal para API Key (placeholder)
        pass

    def toggle_sheets(self):
        # Toggle checkbox state
        if not hasattr(self, '_sheets_toggled'):
            self._sheets_toggled = False

        self._sheets_toggled = not self._sheets_toggled
        for var in self.sheet_vars.values():
            var.set(self._sheets_toggled)

    def show_tree(self, tree_name):
        self.current_tree = tree_name
        if tree_name == "updates":
            self.tree_news.pack_forget()
            self.tree_updates.pack(fill="both", expand=True)
            self.btn_tab_updates.configure(fg_color=["#3B8ED0", "#1F6AA5"])
            self.btn_tab_news.configure(fg_color="gray")
        else:
            self.tree_updates.pack_forget()
            self.tree_news.pack(fill="both", expand=True)
            self.btn_tab_news.configure(fg_color=["#3B8ED0", "#1F6AA5"])
            self.btn_tab_updates.configure(fg_color="gray")

    def select_file(self):
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="Seleccionar Lista de Precios",
            filetypes=[("Archivos Soportados", "*.pdf;*.xlsx;*.xls"), ("PDF", "*.pdf"), ("Excel", "*.xlsx;*.xls")]
        )
        if file_path:
            self.lbl_file_status.configure(text=f"📄 {os.path.basename(file_path)}")
            # Autocompletar proveedor si esta vacio
            if not self.entry_proveedor.get():
                name_clean = os.path.splitext(os.path.basename(file_path))[0].replace('_', ' ')
                self.entry_proveedor.insert(0, name_clean)

            # Ajustar UI dinamicamente segun el tipo
            if file_path.lower().endswith('.pdf'):
                self.sheet_frame.pack_forget()
                self.btn_analyze.configure(command=lambda: self.run_analysis(file_path, "pdf"))
            else:
                import openpyxl
                self.sheet_frame.pack(after=self.load_frame, fill="x", padx=10, pady=5)
                # Clear previous checkboxes
                for widget in self.sheet_checkboxes_frame.winfo_children():
                    widget.destroy()
                self.sheet_vars.clear()

                try:
                    wb = openpyxl.load_workbook(file_path, read_only=True)
                    for sheet in wb.sheetnames:
                        var = ctk.BooleanVar(value=True)
                        cb = ctk.CTkCheckBox(self.sheet_checkboxes_frame, text=sheet, variable=var)
                        cb.pack(side="left", padx=5)
                        self.sheet_vars[sheet] = var
                except Exception:
                    pass

                self.btn_analyze.configure(command=lambda: self.run_analysis(file_path, "excel"))

    def run_analysis(self, file_path, file_type):
        import threading

        self.btn_analyze.configure(text="⏳ Procesando...", state="disabled")

        def worker():
            try:
                if file_type == "pdf":
                    from unificador_listas.src.parser_pdf import parse_pdf_deterministic
                    config = {}
                    if self.combo_precio_baterias.get() == "Usar Costo S/Usada":
                        config["baterias_precio_col"] = "COSTO S/USADA"
                    else:
                        config["baterias_precio_col"] = "FINAL C/USADA"
                    productos = parse_pdf_deterministic(file_path, config)
                else:
                    from unificador_listas.src.parser_excel import parse_excel_deterministic
                    selected_sheets = [s for s, var in self.sheet_vars.items() if var.get()]
                    productos = parse_excel_deterministic(file_path, selected_sheets=selected_sheets if selected_sheets else None)

                # Cross-reference with core logic
                from unificador_listas.src.core_logic import load_maestro_indices, validar_colision
                indices = load_maestro_indices()
                proveedor = self.entry_proveedor.get()

                updates = []
                news = []

                for p in productos:
                    estado = validar_colision(p['codigo_proveedor'], p['descripcion'], proveedor, indices)

                    if estado == "ACTUALIZACION":
                        # Tree Updates columns: ("SKU", "Cod. Prov.", "Descripción", "Marca", "Costo Ant.", "Costo Nvo.", "Var. %")
                        # (We mock Costo Ant y Var for now, real app would pull from db)
                        sku = f"EXISTENTE"
                        costo_ant = "0.00"
                        var_pct = "0%"
                        row_data = (sku, p['codigo_proveedor'], p['descripcion'], p['marca'], costo_ant, p['costo'], var_pct)
                        updates.append(row_data)
                    else:
                        # Tree News columns: ("Proveedor", "Cod. Prov.", "Descripción", "Marca", "Costo")
                        row_data = (proveedor, p['codigo_proveedor'], p['descripcion'], p['marca'], p['costo'])
                        news.append(row_data)

                self.after(0, lambda: self.update_ui_results(updates, news))
            except Exception as e:
                self.after(0, lambda: self.btn_analyze.configure(text="❌ Error", state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def update_ui_results(self, updates, news):
        # Clear tree
        for item in self.tree_updates.get_children():
            self.tree_updates.delete(item)
        for item in self.tree_news.get_children():
            self.tree_news.delete(item)

        for u in updates:
            self.tree_updates.insert("", "end", values=u)
        for n in news:
            self.tree_news.insert("", "end", values=n)

        self.btn_tab_updates.configure(text=f"🔄 Actualizaciones de Precio ({len(updates)})")
        self.btn_tab_news.configure(text=f"✨ Productos Nuevos ({len(news)})")
        self.lbl_resume.configure(text=f"Total: {len(updates) + len(news)}")
        self.btn_analyze.configure(text="⚡ Analizar y Extraer Lista", state="normal")

if __name__ == "__main__":
    app = App()
    app.mainloop()
