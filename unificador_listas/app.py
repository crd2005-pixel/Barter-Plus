import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sqlite3
import pandas as pd
import pdfplumber
import os
import re
import json
import math
from datetime import datetime
import hashlib
from typing import List, Optional
from pydantic import BaseModel, Field
from difflib import SequenceMatcher
try:
    from google import genai
except ImportError:
    genai = None


APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.dirname(
    os.path.abspath(__file__))), "BarterPlus_Unificador")
os.makedirs(APP_DATA_DIR, exist_ok=True)
ERROR_LOG_PATH = os.path.join(APP_DATA_DIR, "error_log.txt")
CONFIG_PATH = os.path.join(APP_DATA_DIR, "config.json")


def registrar_error_seguro(mensaje: str):
    import traceback
    try:
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(mensaje + "\n")
    except Exception:
        pass


PATRON_MEMBRETE = re.compile(
    r'(tel\s*[:.]?|cel\s*[:.]?|fax|0260|0261|44\d[\s-]?\d{3}|sarmiento|san\s+rafael|mendoza|cuit|iva\s|www\.|http|@|distribuidora|hoja\s*\d|p[aá]gina)',
    re.IGNORECASE
)

# App Config
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def extraer_productos_dinamico_multimodal(ruta_archivo: str, proveedor: str, api_key: str, tipo_archivo: str, page_num: int = None, pdf_bytes: bytes = None) -> list:
    if not genai or not api_key:
        return []

    client = genai.Client(api_key=api_key)

    class ProductoExtraido(BaseModel):
        codigo_proveedor: str = Field(
            description="El código real del artículo. PROHIBIDO que empiece con '$' o sea un importe.")
        descripcion: str = Field(
            description="Nombre completo, tipo de producto, medidas, aplicación. PROHIBIDO incluir direcciones, teléfonos, o precios.")
        marca: str = Field(
            description="La marca real del artículo detectada en la fila, columna o sección.")
        costo: float = Field(
            description="El precio unitario final numérico puro (tomar el precio final y omitir valores parciales o entregas de cascos).")

    class ListaProductos(BaseModel):
        productos: List[ProductoExtraido]

    prompt_texto = f"""
    Eres un extractor determinista de listas de precios para el proveedor '{proveedor}'.
    Extrae estrictamente los productos de la imagen o documento adjunto.

    REGLAS ESTRICTAS:
    1. Si una celda o fila agrupa varios códigos apilados verticalmente con sus respectivos amperajes, marcas y precios (como en listas de baterías), desglosa cada código como un producto individual alineando su marca, amperaje, aplicación compartida y su precio correspondiente.
    2. Si una tabla tiene el precio en una columna central y códigos de equivalencia (MANN, FRAM, WEGA, MARENO) a la derecha, toma el precio de la columna Precio e incluye las equivalencias dentro de la descripción.
    3. Ignora membretes comerciales, teléfonos, direcciones, descuentos generales de cabecera y números de página.
    4. Jamás permitas que un código de proveedor contenga el símbolo "$" o parezca un precio.
    5. Jamás permitas que la descripción contenga valores monetarios aislados sin contexto.
    """

    try:
        if tipo_archivo == 'pdf' and pdf_bytes:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    genai.types.Part.from_bytes(
                        data=pdf_bytes, mime_type="application/pdf"),
                    prompt_texto
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ListaProductos
                )
            )
        elif tipo_archivo == 'excel' and pdf_bytes:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    pdf_bytes,
                    prompt_texto
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ListaProductos
                )
            )
        else:
            return []

        text_resp = response.text

        # Clean markdown
        if text_resp.startswith("```json"):
            text_resp = text_resp.strip()[7:-3]
        elif text_resp.startswith("```"):
            text_resp = text_resp.strip()[3:-3]

        data = json.loads(text_resp)

        # Unpack if nested in dict
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list):
                    items_list = v
                    break
            else:
                items_list = [data]  # Fallback
        elif isinstance(data, list):
            items_list = data
        else:
            items_list = []

        extracted = []
        origen = f"Pag {page_num+1}" if page_num is not None else "Documento"

        for item in items_list:
            cod = item.get('codigo_proveedor') or item.get('codigo') or ''
            desc = item.get('descripcion') or item.get('desc') or ''
            marca = item.get('marca', 'GENERICA')
            cost = item.get('costo') or item.get(
                'precio') or item.get('costo_neto') or 0.0

            extracted.append({
                'proveedor': proveedor,
                'codigo_proveedor': cod,
                'descripcion': desc,
                'marca': marca,
                'costo_neto': float(cost) if cost else 0.0,
                'origen': origen
            })

        return extracted
    except Exception as e:
        import traceback
        with open('ERROR_LOG_PATH', 'a', encoding='utf-8') as flog:
            flog.write(
                f"Error multimodal json: {e}\n{traceback.format_exc()}\n")
        return []



def extraer_productos_de_pdf(ruta_pdf: str, proveedor: str, api_key: str) -> list:
    extracted_total = []

    try:
        with open(ruta_pdf, 'rb') as f:
            pdf_bytes = f.read()

        extracted_list = extraer_productos_dinamico_multimodal(ruta_pdf, proveedor, api_key, 'pdf', page_num=0, pdf_bytes=pdf_bytes)

        for prod in extracted_list:
            cod = str(prod['codigo_proveedor']).strip()
            desc = str(prod['descripcion']).strip()
            costo = prod['costo_neto']

            if '$' in cod or re.match(r'^\$?\s*\d{1,3}(?:\.\d{3})+(?:,\d{2})?$', cod):
                continue

            if not desc or desc.startswith("Pag ") and "$" in desc:
                if len(re.sub(r'Pag\s*\d+\s*-\s*\$\s*[\d.,]+', '', desc).strip()) == 0:
                    continue
            if re.match(r'^\$?\s*\d{1,3}(?:\.\d{3})+(?:,\d{2})?$', desc):
                continue

            extracted_total.append(prod)

    except Exception as e:
        import traceback
        registrar_error_seguro(f"Error multimodal pdf: {e}\n{traceback.format_exc()}")

    # CRITICAL: Always fallback if empty
    if not extracted_total:
        extracted_total = _fallback_pdf_determinista(ruta_pdf, proveedor)

    return extracted_total

def extraer_productos_dinamico_multimodal(ruta_archivo: str, proveedor: str, api_key: str, tipo_archivo: str, page_num: int = None, pdf_bytes: bytes = None) -> list:
    if not genai or not api_key:
        return []

    client = genai.Client(api_key=api_key)

    class ProductoExtraido(BaseModel):
        codigo_proveedor: str = Field(
            description="El código real del artículo. PROHIBIDO que empiece con '$' o sea un importe.")
        descripcion: str = Field(
            description="Nombre completo, tipo de producto, medidas, aplicación. PROHIBIDO incluir direcciones, teléfonos, o precios.")
        marca: str = Field(
            description="La marca real del artículo detectada en la fila, columna o sección.")
        costo: float = Field(
            description="El precio unitario final numérico puro (tomar el precio final y omitir valores parciales o entregas de cascos).")

    class ListaProductos(BaseModel):
        productos: List[ProductoExtraido]

    prompt_texto = f"""
    Eres un extractor determinista de listas de precios para el proveedor '{proveedor}'.
    Extrae estrictamente los productos de la imagen o documento adjunto.

    REGLAS ESTRICTAS:
    1. Si una celda o fila agrupa varios códigos apilados verticalmente con sus respectivos amperajes, marcas y precios (como en listas de baterías), desglosa cada código como un producto individual alineando su marca, amperaje, aplicación compartida y su precio correspondiente.
    2. Si una tabla tiene el precio en una columna central y códigos de equivalencia (MANN, FRAM, WEGA, MARENO) a la derecha, toma el precio de la columna Precio e incluye las equivalencias dentro de la descripción.
    3. Ignora membretes comerciales, teléfonos, direcciones, descuentos generales de cabecera y números de página.
    4. Jamás permitas que un código de proveedor contenga el símbolo "$" o parezca un precio.
    5. Jamás permitas que la descripción contenga valores monetarios aislados sin contexto.
    """

    try:
        if tipo_archivo == 'pdf' and pdf_bytes:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    genai.types.Part.from_bytes(
                        data=pdf_bytes, mime_type="application/pdf"),
                    prompt_texto
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ListaProductos
                )
            )
        elif tipo_archivo == 'excel' and pdf_bytes:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    pdf_bytes,
                    prompt_texto
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ListaProductos
                )
            )
        else:
            return []

        text_resp = response.text

        # Clean markdown
        if text_resp.startswith("```json"):
            text_resp = text_resp.strip()[7:-3]
        elif text_resp.startswith("```"):
            text_resp = text_resp.strip()[3:-3]

        data = json.loads(text_resp)

        # Unpack if nested in dict
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list):
                    items_list = v
                    break
            else:
                items_list = [data]  # Fallback
        elif isinstance(data, list):
            items_list = data
        else:
            items_list = []

        extracted = []
        origen = f"Pag {page_num+1}" if page_num is not None else "Documento"

        for item in items_list:
            cod = item.get('codigo_proveedor') or item.get('codigo') or ''
            desc = item.get('descripcion') or item.get('desc') or ''
            marca = item.get('marca', 'GENERICA')
            cost = item.get('costo') or item.get(
                'precio') or item.get('costo_neto') or 0.0

            extracted.append({
                'proveedor': proveedor,
                'codigo_proveedor': cod,
                'descripcion': desc,
                'marca': marca,
                'costo_neto': float(cost) if cost else 0.0,
                'origen': origen
            })

        return extracted
    except Exception as e:
        import traceback
        with open('ERROR_LOG_PATH', 'a', encoding='utf-8') as flog:
            flog.write(
                f"Error multimodal json: {e}\n{traceback.format_exc()}\n")
        return []


def extraer_productos_de_pdf(ruta_pdf: str, proveedor: str, api_key: str) -> list:
    extracted_total = []

    try:
        with open(ruta_pdf, 'rb') as f:
            pdf_bytes = f.read()

        extracted_list = extraer_productos_dinamico_multimodal(
            ruta_pdf, proveedor, api_key, 'pdf', page_num=0, pdf_bytes=pdf_bytes)

        for prod in extracted_list:
            cod = str(prod['codigo_proveedor']).strip()
            desc = str(prod['descripcion']).strip()
            costo = prod['costo_neto']

            if '$' in cod or re.match(r'^\$?\s*\d{1,3}(?:\.\d{3})+(?:,\d{2})?$', cod):
                continue

            if not desc or desc.startswith("Pag ") and "$" in desc:
                if len(re.sub(r'Pag\s*\d+\s*-\s*\$\s*[\d.,]+', '', desc).strip()) == 0:
                    continue
            if re.match(r'^\$?\s*\d{1,3}(?:\.\d{3})+(?:,\d{2})?$', desc):
                continue

            extracted_total.append(prod)

    except Exception as e:
        import traceback
        with open('ERROR_LOG_PATH', 'a', encoding='utf-8') as flog:
            flog.write(
                f"Error multimodal pdf: {e}\n{traceback.format_exc()}\n")

    # CRITICAL: Always fallback if empty
    if not extracted_total:
        extracted_total = _fallback_pdf_determinista(ruta_pdf, proveedor)

    return extracted_total


def limpiar_importe_ar(valor_str):
    if not isinstance(valor_str, str):
        return 0.0
    import re
    s = re.sub(r'[^\d.,]', '', valor_str.strip())
    if not s: return 0.0

    if '.' in s and ',' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    elif '.' in s:
        partes = s.split('.')
        if len(partes) > 1 and len(partes[-1]) == 3:
            s = s.replace('.', '')

    try:
        val = round(float(s), 2)
        return val if val > 0 else 0.0
    except ValueError:
        return 0.0


def _fallback_pdf_determinista(ruta_pdf: str, proveedor: str) -> list:
    extracted_total = []

    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for page_num, page in enumerate(pdf.pages):
                seccion_actual = f"Pag {page_num+1}"
                tables = page.extract_tables()

                if tables:
                    for table in tables:
                        for row in table:
                            extracted, seccion_actual = _process_table_row(
                                row, proveedor, seccion_actual, page_num)
                            if extracted:
                                extracted_total.extend(extracted)

    except Exception as e:
        import traceback
        with open(ERROR_LOG_PATH, 'a', encoding='utf-8') as flog:
            flog.write(
                f"Error _fallback_pdf_determinista: {e}\n{traceback.format_exc()}\n")

    return extracted_total


def _process_table_row(row, proveedor, seccion_actual, page_num):
    extracted = []

    celdas = [str(c).strip() if c is not None else "" for c in row]
    if not any(celdas): return extracted, seccion_actual

    if celdas[0]:
        first_cell_upper = celdas[0].upper()
        if any(first_cell_upper.startswith(x) for x in ["CÓDIGO", "CODIGO", "DESCRIPCIÓN", "DESCRIPCION", "LISTA", "VIGENCIA", "TEL", "E-MAIL", "DESCUENTO"]):
            return extracted, seccion_actual

    # Section check
    has_dollar = any('$' in c for c in celdas)
    has_amount = any(re.search(r'\d{1,3}\.\d{3}', c) for c in celdas)

    if not has_dollar and not has_amount and len([c for c in celdas if c]) in [1, 2]:
        text_val = [c for c in celdas if c][0]
        if not re.search(r'(tel\s*[:.]?|cel\s*[:.]?|fax|cuit|iva\s|www\.|http|@)', text_val, re.IGNORECASE):
            seccion_actual = re.sub(
                r'\d+\s*PRODUCTOS?', '', text_val, flags=re.IGNORECASE).strip()
            return extracted, seccion_actual

    cols_precio = []
    for i, c in enumerate(celdas):
        if '$' in c or re.search(r'\$\s*\d{1,3}(?:\.\d{3})+', c):
            cols_precio.append(i)

    if not cols_precio:
        return extracted, seccion_actual

    # RULE 1: Code from Col 0
    codigo_raw = celdas[0]
    if '$' in codigo_raw:
        return extracted, seccion_actual

    # RULE 2: Multi-line Grouped
    if '\n' in codigo_raw:
        codigos = [c.strip() for c in codigo_raw.split('\n')
                        if c.strip() and '$' not in c]
        precios_str = celdas[cols_precio[-1]]
        precios = re.findall(r'\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?', precios_str)

        if len(codigos) >= 1 and len(precios) == len(codigos):
            amp_col = celdas[1].split('\n') if len(celdas) > 1 else []
            amp_col = [x.strip() for x in amp_col if x.strip()]

            marca_col = celdas[2].split('\n') if len(celdas) > 2 else []
            marca_col = [x.strip() for x in marca_col if x.strip()]

            aplic = celdas[3].replace(
                '\n', ' ').strip() if len(celdas) > 3 else ""

            for i in range(len(codigos)):
                amp = amp_col[i] if i < len(amp_col) else (
                    amp_col[0] if amp_col else "")
                marca = marca_col[i] if i < len(marca_col) else (
                    marca_col[0] if marca_col else "GENERICA")

                desc = f"{seccion_actual} - {amp} - {aplic}".strip(" -")
                desc = re.sub(r'\s{2,}', ' ', desc)

                extracted.append({
                    'proveedor': proveedor,
                    'codigo_proveedor': codigos[i],
                    'descripcion': desc,
                    'marca': marca,
                    'costo_neto': limpiar_importe_ar(precios[i]),
                    'origen': f"Pag {page_num+1}"
                })
            return extracted, seccion_actual

    # RULE 3: Central Price + Equivalences
    if len(cols_precio) == 1:
        idx_p = cols_precio[0]
        codigo_proveedor = celdas[0].replace('\n', ' ').strip()

        match_price = re.search(
            r'\$\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)', celdas[idx_p])
        costo = limpiar_importe_ar(
            match_price.group(1)) if match_price else 0.0

        if costo > 0:
            eqs = []
            celda_precio_parts = celdas[idx_p].split('\n')
            for part in celda_precio_parts:
                if part.strip() and '$' not in part:
                    eqs.append(part.strip())

            for i in range(idx_p + 1, len(celdas)):
                if celdas[i]:
                    eqs.append(celdas[i].replace('\n', ' ').strip())

            desc = f"{seccion_actual} - {celdas[1].replace(chr(10), ' ').strip()}"
            if eqs:
                desc += f" [Eq: {' / '.join(eqs)}]"

            extracted.append({
                'proveedor': proveedor,
                'codigo_proveedor': codigo_proveedor,
                'descripcion': desc,
                'marca': "GENERICA",
                'costo_neto': costo,
                'origen': f"Pag {page_num+1}"
            })

    return extracted, seccion_actual


class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Unificador de Listas - Barter Plus")
        self.geometry("1100x750")

        # Internal State
        self.api_key = ""
        self.master_db_path = None
        self.master_lookup = set()
        self.mapa_por_cod_prov = {}
        self.mapa_por_sku_sufijo = {}
        self.mapa_por_descripcion = {}
        self.last_master_table_name = None

        self.current_file = None
        self.current_file_type = None
        self.excel_data = {}
        self.sheet_vars = {}
        self.extracted_data = []

        self.audit_updates_list = []
        self.audit_new_list = []
        self.current_view_mode = "updates"  # or "new"

        self.load_config()

        # UI Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # The treeview area

        self.setup_header()
        self.setup_control_bar()
        self.setup_dynamic_panel()
        self.setup_unified_audit_view()

        # Connect to default DB quietly
        self.auto_connect_master_db()


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

    def setup_header(self):
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(
            row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        self.header_frame.grid_columnconfigure(1, weight=1)

        lbl_title = ctk.CTkLabel(
            self.header_frame, text="Barter Plus — Unificador de Listas", font=("Roboto", 20, "bold"))
        lbl_title.grid(row=0, column=0, sticky="w")

        # Center Banner
        self.lbl_master_status = ctk.CTkLabel(
            self.header_frame, text="🔴 Sin Conexión", text_color="#ffcc00", font=("Roboto", 13))
        self.lbl_master_status.grid(row=0, column=1, sticky="e", padx=10)

        btn_change_db = ctk.CTkButton(
            self.header_frame, text="Cambiar Base", width=100, height=28, command=self.link_master_db)
        btn_change_db.grid(row=0, column=2, sticky="e", padx=5)

        btn_api_key = ctk.CTkButton(self.header_frame, text="🔑 Configurar API Key", width=140,
                                    height=28, fg_color="#333333", hover_color="#555555", command=self.prompt_api_key)
        btn_api_key.grid(row=0, column=3, sticky="e")

    def prompt_api_key(self):
        dialog = ctk.CTkInputDialog(text="Pega tu Gemini API Key:", title="Configurar API Key")
        key = dialog.get_input()
        if key:
            self.api_key = key.strip()
            self.save_config()
            messagebox.showinfo("API Key", "API Key guardada correctamente.")


    def setup_control_bar(self):
        self.control_frame = ctk.CTkFrame(
            self, fg_color="#2b2b2b", corner_radius=8)
        self.control_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=5)
        self.control_frame.grid_columnconfigure(3, weight=1)

        # Proveedor
        lbl_prov = ctk.CTkLabel(
            self.control_frame, text="Proveedor:", font=("Roboto", 13, "bold"))
        lbl_prov.grid(row=0, column=0, padx=(15, 5), pady=15, sticky="w")

        self.entry_proveedor = ctk.CTkEntry(
            self.control_frame, width=200, placeholder_text="Ej: Seineca, La Casa de las Baterías...")
        self.entry_proveedor.grid(row=0, column=1, padx=5, pady=15, sticky="w")

        # File Loader
        self.btn_load_file = ctk.CTkButton(
            self.control_frame, text="📂 Cargar Lista (Excel / PDF)", width=180, height=35, command=self.load_file)
        self.btn_load_file.grid(row=0, column=2, padx=15, pady=15, sticky="w")

        # Analyze Button
        self.btn_process_file = ctk.CTkButton(self.control_frame, text="⚡ Analizar y Extraer Lista", font=(
            "Roboto", 14, "bold"), fg_color="#28a745", hover_color="#218838", width=220, height=35, command=self.process_file)
        self.btn_process_file.grid(
            row=0, column=3, padx=15, pady=15, sticky="e")

    def setup_dynamic_panel(self):
        self.dynamic_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dynamic_frame.grid(row=2, column=0, sticky="new", padx=15, pady=5)
        # This will hold either a PDF notice or Excel sheet selectors
        self.lbl_pdf_notice = ctk.CTkLabel(
            self.dynamic_frame, text="📄 Archivo PDF listo para procesar.", text_color="#17a2b8", font=("Roboto", 14, "italic"))
        self.sheets_container = ctk.CTkScrollableFrame(
            self.dynamic_frame, height=50, fg_color="#333333", orientation="horizontal")

    def setup_unified_audit_view(self):
        self.audit_frame = ctk.CTkFrame(
            self, fg_color="#1e1e1e", corner_radius=8)
        self.audit_frame.grid(
            row=3, column=0, sticky="nsew", padx=15, pady=(5, 15))
        self.grid_rowconfigure(3, weight=1)
        self.audit_frame.grid_columnconfigure(0, weight=1)
        self.audit_frame.grid_rowconfigure(1, weight=1)

        # Top Bar of Audit
        top_audit = ctk.CTkFrame(self.audit_frame, fg_color="transparent")
        top_audit.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_audit.grid_columnconfigure(3, weight=1)

        self.btn_view_updates = ctk.CTkButton(
            top_audit, text="🔄 Actualizaciones (0)", width=150, fg_color="#0056b3", command=lambda: self.switch_view("updates"))
        self.btn_view_updates.grid(row=0, column=0, padx=(0, 10))

        self.btn_view_new = ctk.CTkButton(top_audit, text="✨ Productos Nuevos (0)",
                                        width=150, fg_color="#444444", command=lambda: self.switch_view("new"))
        self.btn_view_new.grid(row=0, column=1)

        self.entry_search = ctk.CTkEntry(
            top_audit, placeholder_text="🔍 Filtrar por código, marca o descripción...", width=300)
        self.entry_search.grid(row=0, column=3, sticky="e")
        self.entry_search.bind("<KeyRelease>", self.filter_treeview)

        # Treeview
        columns = ("sku", "prov", "cod", "desc", "marca",
                "costo_ant", "costo_nvo", "var")
        self.tree = ttk.Treeview(
            self.audit_frame, columns=columns, show="headings", height=15)

        self.tree.heading("sku", text="SKU")
        self.tree.heading("prov", text="Proveedor")
        self.tree.heading("cod", text="Cód. Prov.")
        self.tree.heading("desc", text="Descripción")
        self.tree.heading("marca", text="Marca")
        self.tree.heading("costo_ant", text="Costo Ant.")
        self.tree.heading("costo_nvo", text="Costo Nvo.")
        self.tree.heading("var", text="% Var")

        self.tree.column("sku", width=100)
        self.tree.column("prov", width=80)
        self.tree.column("cod", width=100)
        self.tree.column("desc", width=300)
        self.tree.column("marca", width=100)
        self.tree.column("costo_ant", width=80, anchor="e")
        self.tree.column("costo_nvo", width=80, anchor="e")
        self.tree.column("var", width=60, anchor="e")

        # Treeview style
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", rowheight=25,
                        fieldbackground="#2b2b2b", bordercolor="#343638", borderwidth=0)
        style.map('Treeview', background=[('selected', '#22559b')])
        style.configure("Treeview.Heading", background="#1f1f1f",
                        foreground="white", relief="flat")
        style.map("Treeview.Heading", background=[('active', '#343638')])

        scrollbar = ttk.Scrollbar(
            self.audit_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)

        self.tree.grid(row=1, column=0, sticky="nsew", padx=(10, 0))
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 10))

        # Footer
        footer = ctk.CTkFrame(self.audit_frame, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=2,
                    sticky="ew", padx=10, pady=10)
        footer.grid_columnconfigure(0, weight=1)

        self.lbl_summary = ctk.CTkLabel(
            footer, text="Total extraído: 0 productos | 0 para actualizar | 0 nuevos", font=("Roboto", 12))
        self.lbl_summary.grid(row=0, column=0, sticky="w")

        self.btn_export = ctk.CTkButton(footer, text="💾 Exportar Excel Unificado (.xlsx)", fg_color="#198754",
                                        hover_color="#146c43", font=("Roboto", 13, "bold"), command=self.export_excel)
        self.btn_export.grid(row=0, column=1, sticky="e")

        # Include a checkbox to include new products in export
        self.chk_var_new = tk.BooleanVar(value=True)
        self.chk_include_new = ctk.CTkCheckBox(
            footer, text="Incluir Nuevos", variable=self.chk_var_new)
        self.chk_include_new.grid(row=0, column=2, sticky="e", padx=(15, 0))

    def switch_view(self, mode):
        self.current_view_mode = mode
        if mode == "updates":
            self.btn_view_updates.configure(fg_color="#0056b3")
            self.btn_view_new.configure(fg_color="#444444")
            self.tree.column("costo_ant", minwidth=80, width=80, stretch=False)
            self.tree.column("var", minwidth=60, width=60, stretch=False)
            self.tree.heading("costo_nvo", text="Costo Nvo.")
        else:
            self.btn_view_updates.configure(fg_color="#444444")
            self.btn_view_new.configure(fg_color="#0056b3")
            self.tree.column("costo_ant", minwidth=0, width=0, stretch=False)
            self.tree.column("var", minwidth=0, width=0, stretch=False)
            self.tree.heading("costo_nvo", text="Costo Final")

        self.filter_treeview()  # Re-render current list

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[(
            "Listas de Precios", "*.xlsx *.xls *.pdf"), ("Excel", "*.xlsx *.xls"), ("PDF", "*.pdf")])
        if not file_path: return

        self.current_file = file_path
        filename = os.path.basename(file_path)

        # Auto-fill provider if empty
        if not self.entry_proveedor.get().strip():
            # Basic cleanup of filename for provider name
            prov_name = re.sub(r'\.(pdf|xlsx|xls)$', '',
                            filename, flags=re.IGNORECASE)
            prov_name = re.sub(r'[-_\d]+', ' ', prov_name).strip().upper()
            if len(prov_name) > 15:
                prov_name = prov_name[:15]
            self.entry_proveedor.insert(0, prov_name)

        if filename.lower().endswith('.pdf'):
            self.current_file_type = 'pdf'

            # Update dynamic panel
            self.sheets_container.grid_forget()
            self.lbl_pdf_notice.configure(
                text=f"📄 Archivo PDF listo para procesar: {filename}")
            self.lbl_pdf_notice.pack(side="left", padx=10, pady=5)

            import PyPDF2
            try:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    pages = len(reader.pages)
                    self.lbl_pdf_notice.configure(
                        text=f"📄 Archivo PDF listo para procesar: {filename} ({pages} páginas)")
            except:
                pass

        else:
            self.current_file_type = 'excel'
            self.lbl_pdf_notice.pack_forget()

            try:
                xl = pd.ExcelFile(file_path)
                self.excel_data = {}

                # Clear previous sheets
                for widget in self.sheets_container.winfo_children():
                    widget.destroy()
                self.sheet_vars.clear()

                self.sheets_container.grid(row=0, column=0, sticky="ew")

                btn_toggle_all = ctk.CTkButton(
                    self.sheets_container, text="Marcar Todas", width=100, fg_color="#555", command=self.select_all_sheets)
                btn_toggle_all.pack(side="left", padx=10)

                for sheet in xl.sheet_names:
                    df = pd.read_excel(xl, sheet_name=sheet, header=None)
                    df = df.dropna(how='all')
                    self.excel_data[sheet] = df

                    var = tk.BooleanVar(value=True)
                    chk = ctk.CTkCheckBox(
                        self.sheets_container, text=sheet, variable=var)
                    chk.pack(side="left", padx=10, pady=5)
                    self.sheet_vars[sheet] = var

            except Exception as e:
                messagebox.showerror(
                    "Error", f"No se pudo cargar el Excel: {e}")

    def filter_treeview(self, event=None):
        search_term = self.entry_search.get().strip().lower()

        for item in self.tree.get_children():
            self.tree.delete(item)

        target_list = self.audit_updates_list if self.current_view_mode == "updates" else self.audit_new_list

        for item in target_list:
            if search_term:
                search_string = f"{item.get('codigo_proveedor', '')} {item.get('descripcion', '')} {item.get('marca', '')} {item.get('sku_interno', '')} {item.get('proveedor', '')}".lower()
                if search_term not in search_string:
                    continue

            if self.current_view_mode == "updates":
                self.tree.insert("", "end", values=(
                    item.get('sku_interno', ''),
                    item.get('proveedor', ''),
                    item.get('codigo_proveedor', ''),
                    item.get('descripcion', ''),
                    item.get('marca', ''),
                    f"${item.get('costo_ant', 0.0):.2f}",
                    f"${item.get('costo_nvo', 0.0):.2f}",
                    f"{item.get('variacion', 0.0):.1f}%"
                ))
            else:
                self.tree.insert("", "end", values=(
                    "NUEVO",
                    item.get('proveedor', ''),
                    item.get('codigo_proveedor', ''),
                    item.get('descripcion', ''),
                    item.get('marca', ''),
                    "",
                    f"${item.get('costo_neto', 0.0):.2f}",
                    ""
                ))


    def auto_connect_master_db(self):
        # 1. Check Config
        if self.master_db_path and os.path.exists(self.master_db_path):
            self.load_master_index_db(self.master_db_path)
            return

        # 2. Check Default BarterPlus paths
        appdata = os.environ.get('APPDATA')
        if not appdata:
            appdata = os.path.expanduser('~/AppData/Roaming')

        paths_to_check = [
            os.path.join(appdata, 'BarterPlus', 'barterplus.db'),
            os.path.join(appdata, 'BarterPlus', 'barterplus')
        ]

        for path in paths_to_check:
            if os.path.exists(path):
                self.master_db_path = path
                self.save_config()
                self.load_master_index_db(path)
                return


    def update_master_banner(self, text=None, is_error=False, detected_cols=None):
        if not hasattr(self, 'lbl_master_status'): return

        if text:
            color = "#ff4444" if is_error else "#00cc66"
            self.lbl_master_status.configure(text=text, text_color=color)
        elif self.master_db_path:
            count = len(self.master_lookup) if hasattr(self, 'master_lookup') else sum(len(v) for v in self.mapa_por_cod_prov.values())
            self.lbl_master_status.configure(text=f"🟢 Base Barter Plus (Solo Lectura): {count} productos", text_color="#00cc66")
        else:
            self.lbl_master_status.configure(text="🔴 Sin Conexión", text_color="#ffcc00")

    def link_master_db(self):
        file_path = filedialog.askopenfilename(filetypes=[("SQLite DB", "*.db *.sqlite *.sqlite3 *")])
        if not file_path: return
        self.master_db_path = file_path
        self.save_config()
        self.load_master_index_db(file_path)

    def link_master_excel(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx *.xls")])
        if not file_path: return
        try:
            df = pd.read_excel(file_path)
            # Find required columns heuristically
            cols = [str(c).lower() for c in df.columns]

            sku_col = next((c for c in df.columns if 'sku' in str(c).lower()), None)
            prov_col = next((c for c in df.columns if 'proveedor' in str(c).lower() and 'cod' not in str(c).lower()), None)
            cod_col = next((c for c in df.columns if 'cod' in str(c).lower() and 'prov' in str(c).lower()), None)
            if not cod_col: cod_col = next((c for c in df.columns if 'codigo' in str(c).lower()), None)
            desc_col = next((c for c in df.columns if 'desc' in str(c).lower()), None)
            marca_col = next((c for c in df.columns if 'marca' in str(c).lower()), None)
            costo_col = next((c for c in df.columns if 'costo' in str(c).lower() or 'precio' in str(c).lower()), None)

            if not all([sku_col, cod_col, desc_col]):
                messagebox.showerror("Error", "No se detectaron las columnas requeridas (SKU, Codigo, Descripcion) en el Excel.")
                return

            self.mapa_por_cod_prov.clear()
            self.mapa_por_sku_sufijo.clear()
            self.mapa_por_descripcion.clear()

            for idx, row in df.iterrows():
                if pd.isna(row.get(sku_col)): continue
                sku = str(row.get(sku_col)).strip()

                prov = str(row.get(prov_col, '')).strip().upper() if prov_col else 'N/A'
                cod_raw = str(row.get(cod_col, '')).strip()
                desc_raw = str(row.get(desc_col, '')).strip()

                prod_data = {
                    'sku_interno': sku,
                    'descripcion': desc_raw,
                    'marca': str(row.get(marca_col, '')),
                    'costo_neto': float(row.get(costo_col, 0.0)) if costo_col and pd.notna(row.get(costo_col)) else 0.0,
                    'proveedor': prov,
                    'codigo_proveedor': cod_raw
                }

                self.index_product(prod_data, sku, cod_raw, desc_raw)

            self.last_master_table_name = None
            self.update_master_banner()
            self.master_db_path = None # Clear DB path if excel is used
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando Excel maestro: {e}")

    def generate_sku(self, proveedor, codigo_proveedor, marca, descripcion):
        prov_prefix = str(proveedor)[:3].upper() if len(str(proveedor)) >= 3 else str(proveedor).upper().ljust(3, 'X')
        cod = str(codigo_proveedor).strip()
        if cod:
            cod_clean = re.sub(r'[^A-Za-z0-9]', '', cod)
            return f"{prov_prefix}-{cod_clean}"
        else:
            base_str = f"{proveedor}{marca}{descripcion}".encode('utf-8')
            md5_hash = hashlib.md5(base_str).hexdigest()[:8].upper()
            return f"{prov_prefix}-{md5_hash}"

    def apply_db_changes(self):
        if not self.audit_updates_list and not self.audit_new_list:
            messagebox.showinfo("Aviso", "No hay datos para aplicar.")
            return

        if not messagebox.askyesno("Confirmar", "¿Está seguro de aplicar los cambios en la base de datos?"):
            return

        try:
            conn = sqlite3.connect(self.local_db_path)
            c = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            inserts = 0

            # Just store history locally
            for item in self.audit_updates_list:
                c.execute('''INSERT INTO historial_unificador
                            (sku_interno, proveedor, codigo_proveedor, descripcion, marca, costo_neto, fecha_actualizacion)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (item['sku_interno'], item.get('proveedor', ''), item['codigo_proveedor'], item['descripcion'], item['marca'], item['costo_nvo'], now))
                inserts += 1

            if self.chk_var_new.get():
                for item in self.audit_new_list:
                    sku = self.generate_sku(item['proveedor'], item['codigo_proveedor'], item['marca'], item['descripcion'])
                    c.execute('''INSERT INTO historial_unificador
                                (sku_interno, proveedor, codigo_proveedor, descripcion, marca, costo_neto, fecha_actualizacion)
                                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                            (sku, item['proveedor'], item['codigo_proveedor'], item['descripcion'], item['marca'], item['costo_neto'], now))
                    inserts += 1

            conn.commit()
            conn.close()

            messagebox.showinfo("Éxito", f"Se guardaron {inserts} registros en el historial local.")

            # Clear temp memory
            self.extracted_data.clear()
            self.audit_updates_list.clear()
            self.audit_new_list.clear()
            for item in self.tree_updates.get_children(): self.tree_updates.delete(item)
            for item in self.tree_new.get_children(): self.tree_new.delete(item)

        except Exception as e:
            messagebox.showerror("Error DB", f"Ocurrió un error guardando en DB: {e}")

    def export_excel(self):
        if not self.audit_updates_list and not self.audit_new_list:
            messagebox.showinfo("Aviso", "No hay datos procesados en la auditoría para exportar.")
            return

        try:
            export_data = []

            for item in self.audit_updates_list:
                export_data.append({
                    'sku_interno': item['sku_interno'],
                    'proveedor': item['proveedor'] if 'proveedor' in item else '',
                    'codigo_proveedor': item['codigo_proveedor'],
                    'descripcion': item['descripcion'],
                    'marca': item['marca'],
                    'costo_neto': item['costo_nvo']
                })

            if self.chk_var_new.get():
                for item in self.audit_new_list:
                    sku = self.generate_sku(item['proveedor'], item['codigo_proveedor'], item['marca'], item['descripcion'])
                    export_data.append({
                        'sku_interno': sku,
                        'proveedor': item['proveedor'],
                        'codigo_proveedor': item['codigo_proveedor'],
                        'descripcion': item['descripcion'],
                        'marca': item['marca'],
                        'costo_neto': item['costo_neto']
                    })

            if not export_data:
                messagebox.showinfo("Aviso", "No hay registros para exportar.")
                return

            df = pd.DataFrame(export_data)

            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel Files", "*.xlsx")],
                initialfile="Padrón_Exportado_Limpio.xlsx"
            )

            if file_path:
                df.to_excel(file_path, index=False, engine='openpyxl')
                messagebox.showinfo("Éxito", f"Archivo limpio exportado correctamente a:\n{file_path}\nTotal: {len(df)} registros.")

        except Exception as e:
            messagebox.showerror("Error de Exportación", f"No se pudo exportar a Excel: {e}")

    def init_local_db(self):
        try:
            conn = sqlite3.connect(self.local_db_path)
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS historial_unificador (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku_interno TEXT,
                    proveedor TEXT,
                    codigo_proveedor TEXT,
                    descripcion TEXT,
                    marca TEXT,
                    costo_neto REAL,
                    fecha_actualizacion TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            messagebox.showerror("Error Local DB", f"Error inicializando base de historial: {e}")

    def index_product(self, prod_data, sku, cod_raw, desc_raw):
        # Index 1: By Normalized Code
        if cod_raw and cod_raw.lower() not in ['none', 'null', '']:
            cod_norm = str(cod_raw).strip().upper().replace(" ", "")
            if cod_norm: self.mapa_por_cod_prov[cod_norm] = prod_data

        # Index 2: By SKU Suffix
        if sku:
            parts = str(sku).split('-')
            sufijo = parts[-1].strip().upper().replace(" ", "") if len(parts) > 1 else str(sku).strip().upper().replace(" ", "")
            if sufijo: self.mapa_por_sku_sufijo[sufijo] = prod_data

        # Index 3: By Normalized Description
        if desc_raw and desc_raw.lower() not in ['none', 'null', '']:
            # Replace multiple spaces with single space, uppercase
            desc_norm = re.sub(r'\s+', ' ', str(desc_raw).strip().upper())
            if desc_norm: self.mapa_por_descripcion[desc_norm] = prod_data

    def load_master_index_db(self, db_path):
        try:
            uri = f"file:{os.path.abspath(db_path)}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Heuristically find the products table
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in c.fetchall()]

            table_name = None
            cols = []

            # Heuristically find the products table by looking at columns
            for t in tables:
                c.execute(f"PRAGMA table_info({t})")
                t_cols = [r['name'].lower() for r in c.fetchall()]

                # Check for product-like columns
                has_code = any(c in t_cols for c in ['sku', 'sku_interno', 'codigo', 'codigo_proveedor'])
                has_desc = any(c in t_cols for c in ['descripcion', 'nombre', 'detalle'])
                has_price = any(c in t_cols for c in ['costo', 'costo_neto', 'precio'])

                if has_code and has_desc and has_price:
                    table_name = t
                    cols = t_cols
                    break

            if not table_name:
                self.update_master_banner("Aviso: No se detectó tabla de inventario válida en la DB maestra.", is_error=True)
                conn.close()
                return

            self.last_master_table_name = table_name

            sku_col = 'sku_interno' if 'sku_interno' in cols else ('sku' if 'sku' in cols else 'codigo')
            prov_col = 'proveedor' if 'proveedor' in cols else ('proveedor_id' if 'proveedor_id' in cols else "''")
            cod_col = 'codigo_proveedor' if 'codigo_proveedor' in cols else ('codigo' if 'codigo' in cols else sku_col)
            desc_col = 'descripcion' if 'descripcion' in cols else ('nombre' if 'nombre' in cols else 'detalle')
            marca_col = 'marca' if 'marca' in cols else ('marca_id' if 'marca_id' in cols else "''")
            costo_col = 'costo_neto' if 'costo_neto' in cols else ('costo' if 'costo' in cols else 'precio')

            detected_cols = f"{sku_col}, {cod_col}, {desc_col}, {costo_col}"
            query = f"SELECT {sku_col} as sku_interno, {prov_col} as proveedor, {cod_col} as codigo_proveedor, {desc_col} as descripcion, {marca_col} as marca, {costo_col} as costo_neto FROM {table_name}"

            c.execute(query)
            rows = c.fetchall()

            self.mapa_por_cod_prov.clear()
            self.mapa_por_sku_sufijo.clear()
            self.mapa_por_descripcion.clear()

            for row in rows:
                sku = str(row['sku_interno']).strip()
                # Use 'N/A' if the column wasn't found or if the data is literally missing
                prov = str(row['proveedor']).strip().upper() if 'proveedor' in row.keys() and row['proveedor'] else 'N/A'
                cod_raw = str(row['codigo_proveedor']) if 'codigo_proveedor' in row.keys() and row['codigo_proveedor'] else ''
                desc_raw = str(row['descripcion']) if 'descripcion' in row.keys() and row['descripcion'] else ''

                prod_data = {
                    'sku_interno': sku,
                    'descripcion': str(desc_raw),
                    'marca': str(row['marca']) if 'marca' in row.keys() else '',
                    'costo_neto': float(row['costo_neto']) if 'costo_neto' in row.keys() and row['costo_neto'] else 0.0,
                    'proveedor': prov,
                    'codigo_proveedor': str(cod_raw)
                }

                self.index_product(prod_data, sku, cod_raw, desc_raw)

            conn.close()
            self.update_master_banner(detected_cols=detected_cols)
        except Exception as e:
            self.update_master_banner(f"Error conectando a DB Maestro: {e}", is_error=True)

    def letter_to_index(self, letter):
        """Convert column letter (A, B, C...) to 0-based index."""
        letter = str(letter).upper().strip()
        if letter.isdigit():
            return int(letter)
        result = 0
        for char in letter:
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1

    def load_excel(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx *.xls")])
        if not file_path: return

        self.current_file = file_path
        self.current_file_type = 'excel'
        self.lbl_file_info.configure(text=f"Cargado: {os.path.basename(file_path)}")

        try:
            xl = pd.ExcelFile(file_path)
            self.excel_data = {}

            # Clear previous sheets
            for widget in self.sheets_frame.winfo_children():
                widget.destroy()
            self.sheet_vars.clear()

            for sheet in xl.sheet_names:
                df = pd.read_excel(xl, sheet_name=sheet, header=None)
                df = df.dropna(how='all')
                self.excel_data[sheet] = df

                var = tk.BooleanVar(value=True)
                chk = ctk.CTkCheckBox(self.sheets_frame, text=sheet, variable=var)
                chk.pack(side="top", anchor="w", padx=10, pady=2)
                self.sheet_vars[sheet] = var

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el Excel: {e}")

    def load_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file_path: return

        self.current_file = file_path
        self.current_file_type = 'pdf'
        self.lbl_file_info.configure(text=f"Cargado: {os.path.basename(file_path)}")

        try:
            # Clear previous sheets UI
            for widget in self.sheets_frame.winfo_children():
                widget.destroy()
            self.sheet_vars.clear()

            # Simple preview message for PDF
            var = tk.BooleanVar(value=True)
            chk = ctk.CTkCheckBox(self.sheets_frame, text="Procesar Todo el PDF", variable=var)
            chk.pack(side="left", padx=10, pady=5)
            self.sheet_vars["PDF_ALL"] = var


        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el PDF: {e}")

    def _is_empty_cell(self, val):
        if pd.isna(val) or val is None: return True
        return str(val).strip() == ""

    def _is_orphan_description(self, text, code):
        t = str(text).strip()
        if not t: return True
        if t == str(code).strip() and t != "": return True
        if len(t) < 5: return True
        # Must have at least one alphabetical word of 3 or more letters
        words = re.findall(r'[A-Za-z]{3,}', t)
        if not words: return True
        return False

    def _is_valid_price(self, val):
        if self._is_empty_cell(val): return False
        s = str(val).strip()
        if s == '$': return False

        # Rule A: Strict numeric/currency check. Reject alphanumeric combos (e.g. 15")
        if not re.match(r'^[\$\s\d.,]+$', s):
            return False

        p = self.limpiar_precio_argentino(val)

        # Anti-Box Quantity Filter: Reject integers < 100 unless explicit $ sign
        if not math.isnan(p) and p < 100.0 and p.is_integer():
            if '$' not in s:
                return False

        return not math.isnan(p) and p > 0.0

    def _extract_segments_from_row(self, row_values):
        # Step B: Divide by empty columns
        segments = []
        current_segment = []
        consecutive_empty = 0

        for val in row_values:
            if self._is_empty_cell(val):
                consecutive_empty += 1
                if consecutive_empty >= 1 and current_segment:
                    segments.append(current_segment)
                    current_segment = []
            else:
                consecutive_empty = 0
                current_segment.append(val)

        if current_segment:
            segments.append(current_segment)

        return segments

    def _process_heuristic_row(self, row_values, context_seccion, proveedor, origen):
        # Check if entire row is empty
        if all(self._is_empty_cell(v) for v in row_values):
            return context_seccion, []

        # Header/Structure breaker: if we see "CODIGO", "PRECIO", etc. we don't clear context entirely,
        # but we definitely don't parse it as a product or title.
        junk_keywords = ["un x caj", "u x bulto", "codigo", "código", "descripcion", "precio", "lista", "linea ", "rubro", "item", "art"]

        segments = self._extract_segments_from_row(row_values)
        extracted = []
        junk_keywords = ["un x caj", "u x bulto", "codigo", "código", "descripcion", "precio", "lista", "linea ", "rubro", "item", "art"]

        # Step A: Context Title
        # Evaluamos por segmento (Isla) en lugar de toda la fila para poder leer "Títulos Side-by-Side"
        if len(segments) > 0:
            all_segments_are_titles = True
            potential_titles = []

            for seg in segments:
                non_empty = [v for v in seg if not self._is_empty_cell(v)]
                if len(non_empty) == 1:
                    val = str(non_empty[0]).strip()
                    val_lower = val.lower()
                    # Ignorar si parece un encabezado de tabla
                    if any(kw in val_lower for kw in ["codigo", "código", "precio", "descrip"]):
                        all_segments_are_titles = False
                        break
                    if not self._is_valid_price(val):
                        # Strict Anti-Letterhead Filter
                        if PATRON_MEMBRETE.search(val):
                            # Membrete detectado, no consideramos este segmento como título válido
                            potential_titles.append(None)
                        else:
                            potential_titles.append(val)
                    else:
                        all_segments_are_titles = False
                        break
                else:
                    all_segments_are_titles = False
                    break

            if all_segments_are_titles:
                # Si todos los segmentos son textos sueltos sin precios, combinamos el primero válido al contexto
                first_valid_title = next((t for t in potential_titles if t is not None), None)
                if first_valid_title:
                    # Ignore if the string is just a date/list header
                    if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', first_valid_title):
                        return context_seccion, []

                    if context_seccion and first_valid_title not in context_seccion:
                        parts = context_seccion.split(" - ")
                        if len(parts) >= 2:
                            return f"{parts[0]} - {first_valid_title}", []
                        else:
                            return f"{context_seccion} - {first_valid_title}", []
                    return first_valid_title, []
                else:
                    return context_seccion, [] # Eran todos membretes

        for seg in segments:
            # Step C: Extract rightmost valid price & Equivalences
            price_idx = -1
            precio_final = 0.0
            mixed_equivalences = []

            # Evaluate from left to right to find the actual designated price column.
            # In some sheets (Seineca), the price is in the middle and equivalences are to the right.
            # In others, price is strictly at the right. We prioritize cells with explicit $.
            explicit_price_idx = -1
            for i in range(len(seg)-1, -1, -1):
                cell_str = str(seg[i]).strip()
                # Support mixed cells like "WK6002\n$4.434"
                if '$' in cell_str:
                    lines = cell_str.split('\n')
                    price_line = next((l for l in lines if '$' in l), None)
                    if price_line and self._is_valid_price(price_line):
                        explicit_price_idx = i
                        precio_final = self.limpiar_precio_argentino(price_line)
                        mixed_equivalences.extend([l.strip() for l in lines if '$' not in l and l.strip()])
                        break
                elif self._is_valid_price(seg[i]):
                    if price_idx == -1: # Keep the rightmost fallback if no explicit $ found yet
                        price_idx = i
                        precio_final = self.limpiar_precio_argentino(seg[i])

            if explicit_price_idx != -1:
                price_idx = explicit_price_idx

            if price_idx == -1: continue # No price in segment

            # Extract Equivalences (columns to the right of the price)
            equivalences = mixed_equivalences.copy()
            for x in seg[price_idx+1:]:
                if not self._is_empty_cell(x) and not self._is_valid_price(x):
                    # Ignore pure measures like 205, 175 if it's right of the price (like battery dimensions)
                    if str(x).strip().isdigit() and len(str(x).strip()) <= 3: continue
                    equivalences.append(str(x).strip())

            # Purge Intermediate Prices (Decimals / Moneda)
            # Remove any float or currency formatted values to the left of the final price
            purged_seg = []
            for cell in seg[:price_idx]:
                if self._is_empty_cell(cell) or str(cell).strip() == '$': continue

                cell_str = str(cell).strip()
                # Purge if it's explicitly a float type, or a string containing '$', or a string with decimals
                if isinstance(cell, float):
                    continue
                if '$' in cell_str:
                    continue
                # If it matches numeric but has a decimal point/comma separating cents, purge it
                if re.match(r'^\d+[.,]\d{1,2}$', cell_str) or re.match(r'^\d{1,3}([.,]\d{3})+[.,]\d{1,2}$', cell_str):
                    continue
                # Filter out pure battery box measures (like 205, 175, 190) from being appended as text
                if cell_str.isdigit() and len(cell_str) <= 3 and int(cell_str) >= 100:
                    continue

                purged_seg.append(cell)

            # Rule B: Ignore Box Quantities in Text
            raw_text_cells = [str(x).strip() for x in purged_seg]
            text_cells = []

            for t in raw_text_cells:
                t_lower = t.lower()
                if t_lower == "un x caj" or t_lower == "u x bulto": continue
                # Discard if it's just a short integer (box quantity)
                if t.isdigit() and len(t) <= 3 and int(t) < 100: continue
                text_cells.append(t)

            if not text_cells and not equivalences: continue

            # Battery special fallback if text_cells is empty but we have equivalences
            if not text_cells and equivalences:
                text_cells = [equivalences.pop(0)]

            codigo = ""
            desc = ""

            # Identify if all text cells are purely measurements/numbers
            all_measures = all(not re.findall(r'[A-Za-z]{3,}', t) for t in text_cells)

            # Rule C: Code vs Description Split
            if all_measures:
                # E.g. ["175/70-13", "175/65-14..."]
                codigo = text_cells[0]
                # Join everything as description, don't drop the first cell if it's all measures
                # Including preserving row specific measurements like "8- 16"
                desc = " / ".join(text_cells)
            elif len(text_cells) >= 2:
                codigo = text_cells[0]
                desc = " - ".join(text_cells[1:]) # Join all subsequent cells preserving specific row measures
            elif len(text_cells) == 1:
                desc = text_cells[0]
                # Check for leading numbers as code (like "300010 Trabasil")
                match_leading = re.search(r'^(\d{4,})\s+', desc)
                if match_leading:
                    codigo = match_leading.group(1)
                else:
                    # Extract trailing numbers as code
                    match_trailing = re.search(r'\b(\d{4,})$', desc)
                    if match_trailing:
                        codigo = match_trailing.group(1)
                    else:
                        codigo = re.sub(r'[^A-Z0-9]', '', desc.upper())[:20]

            # Prevent Code Duplication in Description
            if codigo and desc:
                # Clean up if code was artificially joined inside purely measurements list (like / 30- 45)
                # If desc starts with '/ ', remove it
                desc = re.sub(r'^/\s*', '', desc)

                # Si la descripción empieza exactamente con el código, lo removemos
                pattern = f"^\\s*{re.escape(codigo)}[\\s/\\-]*"
                desc = re.sub(pattern, "", desc, flags=re.IGNORECASE).strip()

            # If description becomes empty after stripping code, fallback to context or code
            if not desc:
                desc = context_seccion if context_seccion else codigo

            cod_lower = codigo.lower()
            desc_lower = desc.lower()
            if any(kw in cod_lower for kw in junk_keywords) or any(kw in desc_lower for kw in junk_keywords):
                continue

            # Context Inheritance
            clean_sheet_name = origen.split(" (")[0] if isinstance(origen, str) else str(origen)
            generic_sheets = ["hoja1", "hoja 1", "sheet1", "sheet 1", "lista", "precios", "pag ", "pág "]
            is_generic_sheet = any(g in clean_sheet_name.lower() for g in generic_sheets)

            if self._is_orphan_description(desc, codigo):
                prefix_parts = []
                if not is_generic_sheet: prefix_parts.append(clean_sheet_name)
                if context_seccion: prefix_parts.append(context_seccion)

                if prefix_parts:
                    desc = f"{' - '.join(prefix_parts)} - {desc}"

            # Append equivalences at the end of the description if any exist
            if equivalences:
                eq_str = " / ".join(equivalences)
                desc = f"{desc} [Eq: {eq_str}]"

            marca = "GENERICA"
            if not is_generic_sheet:
                marca = clean_sheet_name.upper()
            else:
                marca = proveedor.upper()

            extracted.append({
                'proveedor': proveedor,
                'codigo_proveedor': codigo,
                'descripcion': desc,
                'marca': marca,
                'costo_neto': precio_final,
                'origen': origen
            })

        return context_seccion, extracted

    def _log_error(self, message):
        log_path = os.path.join(self.app_dir, 'error_log.txt')
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now()}] {message}\n")
        except Exception as e:
            print(f"No se pudo escribir en log: {e}")

    def _analyze_sheet_structure_with_llm(self, df_sample_str, sheet_name):
        if not genai or not self.api_key:
            return None

        import time
        client = genai.Client(api_key=self.api_key)

        prompt = f"""
Eres un analizador de estructuras de listas de precios.
Analiza la siguiente grilla de datos que representa una hoja de Excel/PDF.
Ignora explícitamente membretes, direcciones (Av. Sarmiento...), teléfonos (Tel: 0260...) y fechas (Vigencia: ...).

Devuelve una lista de bloques de tabla (TableBlock). Por cada bloque indica:
- titulo_categoria: El nombre real del rubro que encabeza ese bloque (e.g. "ABRAZADERAS PERFECTO - Standard Fleje 9mm").
- fila_inicio: Índice 0-based de la fila donde empiezan los datos de productos de este bloque.
- col_codigo: Índice 0-based de la columna del código de proveedor (null si no tiene).
- cols_descripcion: Lista de índices 0-based de columnas que forman el nombre o medida.
- col_precio_final: Índice 0-based numérico de la ÚLTIMA columna de precio (Precio Final), ignorando precios intermedios o unidades por bulto.
- requiere_prefijo_titulo: true si las celdas de descripción de ese bloque solo contienen medidas, talles o aplicaciones cortas (ej. "8- 16", '14"').

Toda la grilla usa índices base-0 exactos: F{{fila}}_C{{columna}}.

MUESTRA GRILLA (Pestaña: {sheet_name}):
{df_sample_str}
"""
        class TableBlock(BaseModel):
            titulo_categoria: str = Field(description="Título real de la categoría/producto")
            fila_inicio: int = Field(description="Índice de fila de inicio de datos")
            col_codigo: Optional[int] = Field(description="Índice de columna de código")
            cols_descripcion: List[int] = Field(description="Índices de columnas de descripción/medida")
            col_precio_final: int = Field(description="Índice de columna del precio final")
            requiere_prefijo_titulo: bool = Field(description="True si la descripción son solo medidas cortas")

        class SheetStructure(BaseModel):
            bloques: List[TableBlock]

        retries = 3
        for attempt in range(retries):
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config={'response_mime_type': 'application/json', 'response_schema': SheetStructure}
                )

                text = response.text
                text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
                text = re.sub(r'```\s*$', '', text)

                return json.loads(text.strip())

            except Exception as e:
                err_msg = str(e)
                self._log_error(f"Error LLM attempt {attempt+1}: {err_msg}")
                if "429" in err_msg or "ResourceExhausted" in err_msg:
                    time.sleep(2 * (attempt + 1)) # Backoff
                else:
                    break
        return None

    def _extract_data_from_blocks(self, df, bloques, proveedor, origen):
        # Sort blocks by start row to determine ends safely
        bloques = sorted(bloques, key=lambda x: x.get('fila_inicio', 0))

        for idx_b, block in enumerate(bloques):
            start = block.get('fila_inicio', 0)
            # If not the last block, the end is just before the next block starts
            end = bloques[idx_b+1].get('fila_inicio', len(df)) - 1 if idx_b + 1 < len(bloques) else len(df) - 1

            titulo = block.get('titulo_categoria', '')
            col_cod = block.get('col_codigo')
            cols_desc = block.get('cols_descripcion', [])
            col_precio = block.get('col_precio_final')
            req_prefijo = block.get('requiere_prefijo_titulo', False)

            if col_precio is None or not cols_desc:
                continue

            last_valid_desc = ""

            for idx in range(start, min(end + 1, len(df))):
                try:
                    row = df.iloc[idx]

                    # Extract Price (with neighbor checking fallback)
                    precio = math.nan
                    precio_raw = None
                    col_precio_real = col_precio

                    if col_precio < len(row):
                        precio_raw = row.iloc[col_precio]
                        precio = self.limpiar_precio_argentino(precio_raw)

                    # Neighbor checking if main price is invalid (compensates for LLM 1-based indexing hallucination)
                    if math.isnan(precio) or precio <= 0.01:
                        # Check left neighbor
                        if col_precio - 1 >= 0 and col_precio - 1 < len(row):
                            p_test = self.limpiar_precio_argentino(row.iloc[col_precio - 1])
                            if not math.isnan(p_test) and p_test > 0.01:
                                precio = p_test
                                precio_raw = row.iloc[col_precio - 1]
                                col_precio_real = col_precio - 1
                        # Check right neighbor if still invalid
                        if (math.isnan(precio) or precio <= 0.01) and col_precio + 1 < len(row):
                            p_test = self.limpiar_precio_argentino(row.iloc[col_precio + 1])
                            if not math.isnan(p_test) and p_test > 0.01:
                                precio = p_test
                                precio_raw = row.iloc[col_precio + 1]
                                col_precio_real = col_precio + 1

                    if math.isnan(precio) or precio <= 0.01: continue

                    # Extract Code
                    codigo = ""
                    if col_cod is not None and col_cod < len(row):
                        cod_val = row.iloc[col_cod]
                        if not pd.isna(cod_val) and str(cod_val).strip():
                            codigo = str(cod_val).strip()

                    # Extract Description
                    desc_parts = []
                    for c_idx in cols_desc:
                        if c_idx < len(row):
                            d_val = row.iloc[c_idx]
                            if not pd.isna(d_val) and str(d_val).strip():
                                # Prevent including the price column itself in the description
                                if c_idx != col_precio_real:
                                    desc_parts.append(str(d_val).strip())

                    desc = " - ".join(desc_parts)

                    # Prevent Code Duplication in Description
                    if codigo and desc:
                        pattern = f"^\\s*{re.escape(codigo)}[\\s/\\-]*"
                        desc = re.sub(pattern, "", desc, flags=re.IGNORECASE).strip()

                    # Missing description but has code (lubricants 20L case)
                    if not desc and last_valid_desc:
                        desc = last_valid_desc
                    elif desc:
                        last_valid_desc = desc

                    if not desc: continue

                    if req_prefijo and titulo:
                        desc = f"{titulo} - {desc}"
                    elif titulo and not any(w in desc.upper() for w in re.findall(r'[A-Za-z]+', titulo.upper())):
                        desc = f"{titulo} - {desc}"

                    # Synthetic Code if missing
                    if not codigo:
                        match_trailing = re.search(r'\b(\d{4,})$', desc)
                        if match_trailing:
                            codigo = match_trailing.group(1)
                        else:
                            codigo = re.sub(r'[^A-Z0-9]', '', desc.upper())[:20]

                    # Context / Brand inheritance
                    clean_sheet_name = origen.split(" (")[0] if isinstance(origen, str) else str(origen)
                    generic_sheets = ["hoja1", "hoja 1", "sheet1", "sheet 1", "lista", "precios", "pag ", "pág "]
                    is_generic_sheet = any(g in clean_sheet_name.lower() for g in generic_sheets)

                    marca = "GENERICA"
                    if not is_generic_sheet:
                        marca = clean_sheet_name.upper()
                    else:
                        marca = proveedor.upper()

                    self.extracted_data.append({
                        'proveedor': proveedor,
                        'codigo_proveedor': codigo,
                        'descripcion': desc,
                        'marca': marca,
                        'costo_neto': precio,
                        'origen': origen
                    })
                except Exception as e:
                    print(f"Extraction error row {idx}: {e}")

    def _fallback_heuristic_parse(self, df, origen, proveedor):
        context_seccion = ""
        items_extracted = 0
        for idx, row in df.iterrows():
            context_seccion, items = self._process_heuristic_row(row.values, context_seccion, proveedor, origen)
            if items:
                self.extracted_data.extend(items)
                items_extracted += len(items)
        return items_extracted

    def process_file(self):
        if not self.current_file:
            messagebox.showwarning("Aviso", "No hay archivo cargado.")
            return

        proveedor = self.entry_proveedor.get().strip().upper()
        if not proveedor:
            messagebox.showwarning("Aviso", "El campo Proveedor es obligatorio.")
            return

        if not self.api_key:
            messagebox.showwarning("Aviso", "Configura la API Key de Gemini primero.")
            return

        self.extracted_data.clear()

        # Updating UI to show progress
        if hasattr(self, 'btn_process_file'):
            original_text = self.btn_process_file.cget("text")
            self.btn_process_file.configure(text="Procesando...", state="disabled")
            self.update()

        try:
            if self.current_file_type == 'excel':
                for sheet, var in self.sheet_vars.items():
                    if not var.get(): continue
                    df = self.excel_data[sheet]

                    if hasattr(self, 'btn_process_file'):
                        self.btn_process_file.configure(text=f"Analizando pestaña: {sheet}")
                        self.update()

                    # Format to string representation using explicit 0-based F_C coords
                    sample_df_str = ""
                    count_rows = 0
                    for idx, row in df.iterrows():
                        if not all(pd.isna(x) or str(x).strip() == "" for x in row):
                            row_vals = [f"F{idx}_C{i}: {x}" for i, x in enumerate(row) if not pd.isna(x) and str(x).strip() != ""]
                            if row_vals:
                                sample_df_str += " | ".join(row_vals) + "\n"
                                count_rows += 1
                        if count_rows >= 100: break

                    if not sample_df_str.strip(): continue

                    initial_count = len(self.extracted_data)
                    # LLM request
                    structure = self._analyze_sheet_structure_with_llm(sample_df_str, sheet)
                    if structure and 'bloques' in structure:
                        self._extract_data_from_blocks(df, structure['bloques'], proveedor, sheet)

                    # FALLBACK if LLM fails to extract any valid products
                    if len(self.extracted_data) == initial_count:
                        self._log_error(f"Fallback activado en pestaña '{sheet}': IA devolvió 0 productos válidos.")
                        self._fallback_heuristic_parse(df, sheet, proveedor)

                messagebox.showinfo("Proceso Terminado", f"Se extrajeron {len(self.extracted_data)} productos válidos de Excel.")
                self.populate_audit_tables()

            elif self.current_file_type == 'pdf':
                extracted_list = extraer_productos_de_pdf(self.current_file, proveedor, self.api_key)
                if extracted_list:
                    self.extracted_data.extend(extracted_list)
                    messagebox.showinfo("Proceso Terminado", f"Se extrajeron {len(extracted_list)} productos válidos de PDF.")
                self.populate_audit_tables()

        except Exception as e:
            import traceback
            err_str = traceback.format_exc()
            self._log_error(err_str)
            messagebox.showerror("Error de Extracción", f"Ocurrió un error inesperado en PDF:\n{e}\n\nRevisa el archivo error_log.txt")

        finally:
            if hasattr(self, 'btn_process_file'):
                self.btn_process_file.configure(text=original_text, state="normal")
                self.update()

    def limpiar_descripcion_final(self, desc: str, cod_prov: str) -> str:
        if not desc:
            return ""
        desc = str(desc).strip()
        # Remove repeated provider code prefix
        if cod_prov:
            patron_cod = re.compile(r'^' + re.escape(str(cod_prov).strip()) + r'[\s\-:/]+', re.IGNORECASE)
            desc = patron_cod.sub('', desc).strip()
        # Collapse multiple spaces
        desc = re.sub(r'\s{2,}', ' ', desc)
        return desc

    def _is_semantic_match(self, desc1: str, desc2: str) -> bool:
        if not desc1 or not desc2: return False

        d1_up = str(desc1).upper()
        d2_up = str(desc2).upper()

        # Tokenize words >= 4 characters
        tokens1 = set(re.findall(r'\b[A-Za-z0-9]{4,}\b', d1_up))
        tokens2 = set(re.findall(r'\b[A-Za-z0-9]{4,}\b', d2_up))

        # Direct token intersection check
        if tokens1 and tokens2 and tokens1.intersection(tokens2):
            return True

        # Sequence matcher fallback for general similarity
        ratio = SequenceMatcher(None, d1_up, d2_up).ratio()
        return ratio >= 0.45

    def _is_prefix_match(self, proveedor_excel: str, marca_excel: str, sku_db: str) -> bool:
        if not sku_db: return False
        sku_prefix = str(sku_db).split('-')[0].upper()

        # If it's a known generic/unrelated prefix, and the incoming is explicitly from a different brand/provider
        # e.g., GEN-, MAN- vs WALKER (WAL)
        prov = str(proveedor_excel).upper()
        marca = str(marca_excel).upper()

        # Heuristic mapping for prefix rejection
        # If incoming is highly specific (WALKER -> WAL), but SKU is MAN- or GEN-
        # This acts as a strict guard.

        # If sku_prefix matches the first 3 letters of provider or brand, it's a safe match
        if prov[:3] == sku_prefix or marca[:3] == sku_prefix:
            return True

        # If SKU prefix is something completely unrelated to the incoming data (like MAN or GEN when expecting WAL)
        # This will be used in combination with semantic match, so returning False forces the semantic check to pass.
        return False

    def limpiar_precio_argentino(self, valor_crudo):
        if pd.isna(valor_crudo): return math.nan

        if not isinstance(valor_crudo, str):
            try:
                val = float(valor_crudo)
                if math.isnan(val): return math.nan
                return val
            except (ValueError, TypeError):
                return math.nan

        # Rule: If cell has a $ sign, only keep what's AFTER the last $ sign to prevent
        # adjacent columns (like a box quantity 3) from sticking to the price ($ 9.025,70 -> 39.025,70)
        s = str(valor_crudo).strip()
        if '$' in s:
            s = s.split('$')[-1]

        s = re.sub(r'[^\d.,]', '', s.strip())
        if not s:
            return math.nan

        if '.' in s and ',' in s:
            if s.rfind(',') > s.rfind('.'):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif ',' in s:
            s = s.replace(',', '.')
        elif '.' in s:
            partes = s.split('.')
            if len(partes) > 1 and len(partes[-1]) == 3:
                s = s.replace('.', '')

        try:
            val = round(float(s), 2)
            if math.isnan(val): return math.nan
            return val
        except ValueError:
            return math.nan


    def populate_audit_tables(self):
        self.audit_updates_list.clear()
        self.audit_new_list.clear()

        for item in self.extracted_data:
            prov = item['proveedor']
            cod = item['codigo_proveedor']
            desc = item['descripcion']
            marca = item['marca']
            costo = item['costo_neto']

            # Double Lock Check
            match_sku = None
            match_data = None

            candidates = []
            if prov in self.mapa_por_cod_prov and cod in self.mapa_por_cod_prov[prov]:
                candidates.extend(self.mapa_por_cod_prov[prov][cod])

            cod_suffix = str(cod).split('-')[-1].upper()
            if cod_suffix in self.mapa_por_sku_sufijo:
                candidates.extend(self.mapa_por_sku_sufijo[cod_suffix])

            def validate_match(candidate):
                sku_cand = candidate['sku_interno']
                # Prefijos y semantica
                if self._is_prefix_match(prov, marca, sku_cand):
                    return True
                if self._is_semantic_match(desc, candidate['descripcion']):
                    return True
                return False

            for cand in candidates:
                if validate_match(cand):
                    match_sku = cand['sku_interno']
                    match_data = cand
                    break

            if not match_sku and desc in self.mapa_por_descripcion:
                match_sku = self.mapa_por_descripcion[desc]['sku_interno']
                match_data = self.mapa_por_descripcion[desc]

            if match_sku:
                costo_ant = match_data.get('costo_neto', 0.0)
                var = 0.0
                if costo_ant > 0:
                    var = ((costo - costo_ant) / costo_ant) * 100

                self.audit_updates_list.append({
                    'sku_interno': match_sku,
                    'proveedor': prov,
                    'codigo_proveedor': cod,
                    'descripcion': desc,
                    'marca': marca,
                    'costo_ant': costo_ant,
                    'costo_nvo': costo,
                    'variacion': var
                })
            else:
                self.audit_new_list.append(item)

        # Update summary labels
        total_extracted = len(self.extracted_data)
        total_upd = len(self.audit_updates_list)
        total_new = len(self.audit_new_list)

        if hasattr(self, 'lbl_summary'):
            self.lbl_summary.configure(text=f"Total extraído: {total_extracted} productos | {total_upd} para actualizar | {total_new} nuevos")
            self.btn_view_updates.configure(text=f"🔄 Actualizaciones ({total_upd})")
            self.btn_view_new.configure(text=f"✨ Productos Nuevos ({total_new})")

        self.filter_treeview()

if __name__ == "__main__":
    app = App()
    app.mainloop()
import re
import math
import pdfplumber
import traceback
