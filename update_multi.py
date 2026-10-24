with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("with open('unificador_listas/error_log.txt', 'a', encoding='utf-8') as flog:\n            flog.write(f\"Error multimodal json: {e}\\n{traceback.format_exc()}\\n\")", "registrar_error_seguro(f\"Error multimodal json: {e}\\n{traceback.format_exc()}\")")

with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
