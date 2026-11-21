# Reglas del Proyecto Unificador de Listas

1. **MOTOR 100% LOCAL Y DETERMINISTA:**
   - Este módulo está diseñado para procesar archivos PDF y Excel usando reglas predefinidas y un sistema de aprendizaje basado en perfiles (`GestorPerfilesEntrenamiento`). No se debe invocar a ninguna API externa (ni de IA ni de otro tipo).

2. **SISTEMA DE APRENDIZAJE LOCAL:**
   - Las configuraciones específicas de cómo parsear la lista de un proveedor se deben almacenar y recuperar del archivo local `perfiles_entrenamiento.json` en `%APPDATA%\BarterPlus_Unificador\`.

3. **CUMPLIMIENTO DE REGLAS GLOBALES:**
   - Todas las reglas definidas en el `AGENTS.md` de la raíz del proyecto aplican aquí también, en particular el aislamiento de datos (uso de AppData) y el acceso a la base de datos principal (`barterplus.db`) en modo de solo lectura.
