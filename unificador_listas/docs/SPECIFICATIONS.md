# Barter Plus — Unificador de Listas - SPECIFICATIONS

## PRD (Product Requirements Document)

- **Propósito:** Unificar listas de precios heterogéneas de proveedores (archivos Excel `.xlsx`/`.xls` con múltiples pestañas y archivos `.pdf` con tablas simples, tablas multi-línea o texto plano) cruzándolas contra el padrón actual de `barterplus.db` (2919+ artículos).
- **Salidas del Sistema:**
  1. **Auditoría Pre-Guardado en Pantalla:** Separada claramente en dos vistas con contadores en vivo: `🔄 Actualizaciones de Precio (Existentes)` y `✨ Productos Nuevos Detectados`.
  2. **Exportación a Excel Unificado (`.xlsx`):** Archivo limpio listo para importar en el sistema principal de gestión, con formato profesional y hojas separadas para Actualizaciones y Altas Nuevas.

## TRD (Technical Requirements Document)

- **Stack:** Python 3.11+, `customtkinter`, `tkinter.ttk`, `sqlite3` (URI Read-Only), `openpyxl`, `pdfplumber`, `google-genai` (`gemini-2.5-flash`), `pydantic`, `pillow`, `pyinstaller`.
- **Arquitectura de Extracción Dual (Híbrida + Determinista):**
  - **En PDF:**
    1. *Motor Determinista Especializado (Primera línea rápida y exacta para tablas estructuradas):* Usa `pdfplumber` con soporte nativo para desglosar celdas multi-línea (`\n`) y detectar precios en columnas centrales con equivalencias a la derecha.
    2. *Agente Multimodal Gemini 2.5 Flash (Complemento dinámico para PDFs sin bordes o diseños atípicos):* Si un PDF o página no posee estructura tabular reconocible por `pdfplumber`, envía la página o el texto con layout a `gemini-2.5-flash` con esquema JSON estricto, validando luego cada fila en Python.
  - **En Excel:**
    - Escaneo de pestañas seleccionadas con `openpyxl` (`data_only=True`), detección inteligente de cabeceras, soporte para tablas paralelas o listas por medidas y asistencia del Agente IA para mapear columnas desconocidas.

## UI/UX Design (Interfaz Dinámica, Limpia y Directa)

1. **Header Superior Compacto (1 sola fila):**
   - Izquierda: Título `"Barter Plus — Unificador de Listas"` + Selector rápido de columna de precio en baterías (`[Usar Final C/Usada | Usar Costo S/Usada]`).
   - Centro: Indicador `"🟢 Base Barter Plus (Solo Lectura): X productos"` + botón discreto `"Cambiar Base"`.
   - Derecha: Botón `"🔑 API Key"` que abre un diálogo modal para guardar la clave en `config.json` (sin ocupar lugar fijo en la pantalla principal).
2. **Panel de Carga Unificado (1 sola fila de controles):**
   - Campo `Proveedor` (si está vacío al elegir archivo, se autocompleta limpiando el nombre del archivo).
   - Un **ÚNICO botón `"📂 Seleccionar Lista (Excel o PDF)"`** (`*.xlsx *.xls *.pdf`).
   - Botón principal destacado en verde: **`"⚡ Analizar y Extraer Lista"`**.
   - **Selector Dinámico de Pestañas (Colapsable):**
     - Si se carga un **PDF**, este panel permanece **OCULTO** (solo muestra `"📄 PDF listo para procesar"`), dejando todo el espacio vertical para la tabla de resultados.
     - Si se carga un **Excel**, muestra los checkboxes de las hojas con botón `"Marcar / Desmarcar Todas"`.
3. **Área Principal de Auditoría y Exportación (En la misma vista):**
   - Barra superior de la tabla con:
     - Botón pestaña **`"🔄 Actualizaciones de Precio (X)"`** (Columnas: `SKU | Cod. Prov. | Descripción | Marca | Costo Ant. | Costo Nvo. | Var. %`).
     - Botón pestaña **`"✨ Productos Nuevos (Y)"`** (Columnas: `Proveedor | Cod. Prov. | Descripción | Marca | Costo`).
     - **Buscador en Tiempo Real (`🔍 Filtrar por código, marca o descripción...`)** que filtra la tabla instantáneamente al escribir.
   - **Footer de Acción Directa:**
     - Resumen de totales + Botón grande **`"💾 Exportar Excel Unificado (.xlsx)"`** directamente accesible sin cambiar de pestaña.

## AppFlow (Flujo Operativo Paso a Paso)

1. **Inicio:** Carga `config.json` desde `%APPDATA%\BarterPlus_Unificador\`, conecta en `mode=ro` a `%APPDATA%\BarterPlus\barterplus.db` y construye 3 índices en memoria (`por_sku`, `por_cod_prov`, `por_descripcion_normalizada`).
2. **Selección de Archivo:** El usuario elige un `.pdf` o `.xlsx`. Si `Proveedor` está vacío, sugiere el nombre del archivo. Si es Excel, lista sus hojas; si es PDF, oculta el panel de hojas.
3. **Extracción y Validación:** Al pulsar `"⚡ Analizar y Extraer Lista"`, corre en hilo secundario mostrando el progreso real en el botón. Aplica el candado post-extracción: descarta cualquier fila cuyo `codigo_proveedor` tenga `$` o sea numérico de precio, limpia importes argentinos (`$ 105.361` -> `105361.0`) y cruza contra los índices con el doble candado anti-colisión.
4. **Auditoría y Exportación:** Muestra los resultados en la tabla `Treeview`, permite filtrar en vivo y exporta el `.xlsx` final con `openpyxl`.

## Backend Schema (Estructuras de Datos)

1. **Tabla leída en `barterplus.db` (`mode=ro`):**
   - `productos`: Detectar dinámicamente nombres de columnas (`id`/`sku`/`codigo`, `codigo_proveedor`/`cod_prov`, `descripcion`/`nombre`, `marca`/`rubro`, `costo`/`precio_costo`).
2. **Diccionario Estándar de Producto Extraído:**
   ```python
   {
       "codigo_proveedor": str,  # Ej: "UB 450", "SAF95019" (PROHIBIDO contener '$')
       "descripcion": str,       # Ej: "SERVICIO PESADO - 12X100 - WILLARD - 504 DIESEL - TRACTOR - CAMIONES"
       "marca": str,             # Ej: "WILLARD", "MOURA", "LEMOM PREMIUM", "SEINECA"
       "costo": float            # Ej: 105361.0 (Siempre > 0)
   }
   ```
