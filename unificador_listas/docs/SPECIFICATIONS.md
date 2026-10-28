# Especificación de Arquitectura: Sistema de Aprendizaje Local

## GestorPerfilesEntrenamiento

El `GestorPerfilesEntrenamiento` es la clase central responsable de manejar la configuración de extracción de datos por proveedor y tipo de archivo, garantizando que el Unificador de Listas funcione de manera 100% determinista y offline, sin depender de IAs externas.

### Almacenamiento

El archivo de configuración debe guardarse estrictamente en la siguiente ruta:
`%APPDATA%\BarterPlus_Unificador\perfiles_entrenamiento.json`

### Estructura de Datos y Jerarquía

La estructura interna de datos utiliza claves jerárquicas con el siguiente formato:
`"{proveedor_normalizado}::{tipo_archivo}::{identificador_hoja_o_tabla}"`

- `tipo_archivo`: Puede ser `"PDF"` o `"EXCEL"`.
- `identificador_hoja_o_tabla`: El nombre de la pestaña en el caso de Excel, o `"PDF_GENERAL"` / índice de la tabla en el caso de PDFs.

### Metadatos de Nivel Superior

Además de las configuraciones específicas por hoja/tabla, se guardan metadatos a nivel de tipo de archivo:
- `"{proveedor_normalizado}::EXCEL"`: Contiene la clave `"hojas_activas"` (lista de pestañas válidas).
- `"{proveedor_normalizado}::PDF"`: Contiene la clave `"paginas_ignoradas"` (lista de índices de páginas a saltar).

### Esquema del Perfil

Cada perfil de entrenamiento almacenado debe cumplir con la siguiente estructura de diccionario en Python:

```python
{
    "activa": True,                      # Booleano: Si la pestaña/tabla está marcada para ser procesada
    "col_codigo": 0,                     # Entero: Índice de la columna del Código del Proveedor
    "col_descripcion": 1,                # Entero: Índice de la columna de Descripción
    "col_marca": None,                   # Entero (o None): Índice de la columna de Marca. Si es None, usar `marca_fija`
    "col_precio": 2,                     # Entero: Índice de la columna de Costo/Precio
    "cols_equivalencias": [3, 4, 5, 6],  # Lista de enteros: Índices de columnas para concatenar como equivalencias
    "fila_inicio": 1,                    # Entero: Número de filas de encabezado a omitir
    "filas_pie_ignorar": 0,              # Entero: Número de filas al pie de página a omitir
    "paginas_ignoradas": [],             # Lista de enteros: Páginas a omitir en PDFs (1-based index)
    "modo_multiline_baterias": False,    # Booleano: Si se debe aplicar lógica especial para celdas multilinea (ej. baterías)
    "marca_fija": ""                     # String: Marca a aplicar si `col_marca` es None
}
```

## Conexión a Base de Datos Principal

Cualquier consulta que se deba hacer a la base de datos principal (`barterplus.db`) para referencias (ej. códigos existentes) **debe** utilizar una URI con modo de solo lectura (`?mode=ro`). Esto es para garantizar que este módulo jamás altere los datos transaccionales del sistema principal.
