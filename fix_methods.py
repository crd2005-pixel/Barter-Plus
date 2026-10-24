with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

config_methods = """
    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    conf = json.load(f)
                    self.api_key = conf.get("api_key", "")
                    self.master_db_path = conf.get("master_db_path")
            except Exception:
                pass

    def save_config(self):
        try:
            with open(CONFIG_PATH, 'w') as f:
                json.dump({"api_key": self.api_key, "master_db_path": self.master_db_path}, f)
        except Exception:
            pass
"""

init_idx = content.find("def setup_header")
if init_idx != -1:
    content = content[:init_idx] + config_methods + "\n" + content[init_idx:]
    with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Injected config methods.")
