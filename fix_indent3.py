with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
    for line in lines:
        if line.startswith("    def update_master_banner"):
            f.write(line)
        else:
            f.write(line)
