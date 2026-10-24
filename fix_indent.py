with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all `self.lbl_master_info` to `self.lbl_master_status` since we renamed it in setup_header
content = content.replace("lbl_master_info", "lbl_master_status")

# We will also just delete update_master_banner completely and move its simple logic.
# Find `def update_master_banner` up to `def link_master_db`
start_idx = content.find("def update_master_banner")
end_idx = content.find("def link_master_db")

if start_idx != -1 and end_idx != -1:
    new_banner_logic = """
    def update_master_banner(self, text=None, is_error=False, detected_cols=None):
        if not hasattr(self, 'lbl_master_status'): return

        if text:
            color = "#ff4444" if is_error else "#00cc66"
            self.lbl_master_status.configure(text=text, text_color=color)
        elif self.master_db_path:
            count = len(self.master_lookup) if hasattr(self, 'master_lookup') else sum(len(v) for v in self.mapa_por_cod_prov.values())
            self.lbl_master_status.configure(text=f"🟢 Base Barter Plus (Solo Lectura): {count} productos", text_color="#00cc66")
        else:
            self.lbl_master_status.configure(text="🔴 Sin Conexión", text_color="#ffcc00")

"""
    content = content[:start_idx] + new_banner_logic + content[end_idx:]
    with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
        f.write(content)
