# Barter Plus — Unificador de Listas - AGENTS.md

## Reglas Inquebrantables del Proyecto

1. **Regla 1 (Cero Escritura en Base Productiva):**
   `barterplus.db` solo se abre con `?mode=ro` (Solo Lectura) mediante URI SQLite.
   Bajo ninguna circunstancia este programa puede ejecutar `INSERT`, `UPDATE`, `DELETE`, `ALTER` o `DROP` sobre `barterplus.db`.

2. **Regla 2 (Rutas Seguras):**
   Ningún archivo se lee ni escribe usando el prefijo `'unificador_listas/'` de manera relativa. Todo archivo de estado (config, base interna, logs) va a `%APPDATA%\BarterPlus_Unificador\`.

3. **Regla 3 (Candado de Datos):**
   Ningún producto válido puede tener `$` en `codigo_proveedor` ni `costo <= 0`.

4. **Regla 4 (Autoverificación Pre-Commit):**
   Antes de dar por terminada cualquier tarea, ejecutar obligatoriamente `python unificador_listas/test_verificacion.py` y verificar que pase al 100%.
