with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
    for line in lines:
        if line.startswith("    def prompt_api_key"):
            f.write(line)
        else:
            f.write(line)
