# Reglas Absolutas del Proyecto BarterPlus - Unificador

1. **PROHIBICIÓN ABSOLUTA DE IA EXTERNA O CONEXIONES DE RED:**
   - Está terminantemente prohibido importar o usar `google-genai`, `openai`, `requests` o pedir `API Key`. Todo el programa debe funcionar 100% offline y local.

2. **PROHIBICIÓN ABSOLUTA DE ESCRITURA EN LA BASE PRINCIPAL (`barterplus.db`):**
   - La base productiva (`%APPDATA%\BarterPlus\barterplus.db`) debe abrirse **EXCLUSIVAMENTE EN MODO SOLO LECTURA** mediante URI SQLite:
     `sqlite3.connect(f"file:{os.path.abspath(db_path).replace(chr(92), '/')}?mode=ro", uri=True)`
   - Prohibido ejecutar `INSERT`, `UPDATE`, `DELETE`, `ALTER` o `DROP` sobre `barterplus.db`.

3. **AISLAMIENTO DE ARCHIVOS EN `%APPDATA%\BarterPlus_Unificador\`:**
   - Todos los archivos propios del programa (`config.json`, `perfiles_entrenamiento.json`, `error_log.txt`) deben guardarse usando `os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "BarterPlus_Unificador", nombre_archivo)`.
   - Prohibido escribir rutas relativas con prefijo como `'unificador_listas/error_log.txt'`.
