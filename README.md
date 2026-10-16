# Guía de Validación - Unificador de Listas Determinista

El Unificador de Listas es una herramienta estrictamente determinista que garantiza la integridad de la base de datos `inventario_barter.db` y protege los códigos internos existentes.

## 1. Protección de SKUs y Códigos Existentes
El sistema genera un `master_lookup` que asocia la clave compuesta de `(proveedor, codigo_proveedor)` con el `sku_interno` correspondiente.
El sistema usa un código normalizado (`upper()` y sin espacios) antes de hacer la búsqueda para que sea inmune a la suciedad del archivo de entrada (`OIL-123` y `oil - 123` apuntan al mismo SKU existente).

Si un producto se encuentra en el índice maestro (`master_lookup`), el programa trata la fila únicamente como una **actualización**. Esto asegura que el `sku_interno`, `descripcion` y `marca` del producto original **no se alteran** en la BD de Barter Plus. Solo el campo `costo_neto` es modificado y se renueva su `fecha_actualizacion`.

## 2. Productos Nuevos Seguros
Únicamente si la combinación normalizada `(proveedor, codigo_proveedor)` *no* se encuentra en la base de datos se clasifica la fila como un producto nuevo.
En este caso, la herramienta genera de forma estructurada y determinista un `sku_interno` nuevo mediante el prefijo del proveedor y código o con un MD5 del nombre (ej., `PROV-COD123`), de modo que no se interfiere con los identificadores autonuméricos previos ni con IDs incrementales de otros sistemas.

## 3. Extracción Segura Anti-Desfase (Cruce por Índice Horizontal)
Al importar de Excel (`pandas`) o PDF (`pdfplumber` vía extract_tables y extract_lines con un separador de doble espacio):
* Si una fila extraída se encuentra vacía o el código coincide con valores cabecera como "Código" o "Item", se descarta la fila.
* El campo "precio/costo" debe tener un valor numérico depurado mayor a 0 usando la función `limpiar_precio_argentino()`. Si esta condición falla en la extracción, la fila completa se omite para prevenir falsos registros a coste cero.
