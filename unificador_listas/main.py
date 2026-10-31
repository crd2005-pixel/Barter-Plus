import os
import json
import sqlite3
import re
import traceback
import pandas as pd
import pdfplumber
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Menu
import threading
import math
import time

def limpiar_precio_argentino(valor_crudo):
    if not isinstance(valor_crudo, str):
        try:
            return float(valor_crudo)
        except (ValueError, TypeError):
            return 0.0
    import re
    s = re.sub(r'[^\d.,]', '', str(valor_crudo).strip())
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
            if len(partes[0]) <= 2 and int(partes[0]) < 10:
                s = partes[0] + "." + partes[-1][:2]
            else:
                s = s.replace('.', '')

    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0

class GestorPerfilesEntrenamiento:
    def __init__(self):
        self.appdata_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "BarterPlus_Unificador")
        self.archivo_perfiles = os.path.join(self.appdata_dir, "perfiles_entrenamiento.json")
        self._asegurar_directorio()
        self.perfiles = self.cargar_perfiles()

    def _asegurar_directorio(self):
        os.makedirs(self.appdata_dir, exist_ok=True)
        if not os.path.exists(self.archivo_perfiles):
            with open(self.archivo_perfiles, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=4)

    def cargar_perfiles(self):
        try:
            with open(self.archivo_perfiles, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def guardar_perfiles(self):
        try:
            with open(self.archivo_perfiles, "w", encoding="utf-8") as f:
                json.dump(self.perfiles, f, indent=4)
        except Exception as e:
            print(f"Error guardando perfiles: {e}")

    def obtener_perfil(self, proveedor, tipo_archivo, identificador):
        clave = f"{str(proveedor).strip().upper()}::{str(tipo_archivo).strip().upper()}::{str(identificador).strip()}"
        return self.perfiles.get(clave, self.perfil_por_defecto())

    def guardar_perfil(self, proveedor, tipo_archivo, identificador, perfil_datos):
        clave = f"{str(proveedor).strip().upper()}::{str(tipo_archivo).strip().upper()}::{str(identificador).strip()}"
        self.perfiles[clave] = perfil_datos
        self.guardar_perfiles()

    def actualizar_metadatos_excel(self, proveedor, hojas_activas):
        clave = f"{str(proveedor).strip().upper()}::EXCEL"
        if clave not in self.perfiles:
            self.perfiles[clave] = {}
        self.perfiles[clave]["hojas_activas"] = hojas_activas
        self.guardar_perfiles()

    def obtener_metadatos_excel(self, proveedor):
        clave = f"{str(proveedor).strip().upper()}::EXCEL"
        return self.perfiles.get(clave, {}).get("hojas_activas", [])

    def actualizar_metadatos_pdf(self, proveedor, paginas_ignoradas):
        clave = f"{str(proveedor).strip().upper()}::PDF"
        if clave not in self.perfiles:
            self.perfiles[clave] = {}
        self.perfiles[clave]["paginas_ignoradas"] = paginas_ignoradas
        self.guardar_perfiles()

    def obtener_metadatos_pdf(self, proveedor):
        clave = f"{str(proveedor).strip().upper()}::PDF"
        return self.perfiles.get(clave, {}).get("paginas_ignoradas", [])

    @staticmethod
    def perfil_por_defecto():
        return {
            "activa": True,
            "col_codigo": 0,
            "col_descripcion": 1,
            "col_marca": None,
            "col_precio": 2,
            "cols_equivalencias": [],
            "fila_inicio": 1,
            "filas_pie_ignorar": 0,
            "paginas_ignoradas": [],
            "modo_multiline_baterias": False,
            "marca_fija": "",
            "modo_lectura_pdf": "auto_desglosado",
            "nombres_cabecera_aprendidos": {},
            "reglas_markdown": []
        }

class MotorCruceBarterPlus:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "BarterPlus", "barterplus.db")
        self.db_path = db_path
        self.productos_db = []
        self._cargar_db()

    def _cargar_db(self):
        db_uri = f"file:{os.path.abspath(self.db_path).replace(chr(92), '/')}?mode=ro"
        try:
            conn = sqlite3.connect(db_uri, uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT id, codigo_proveedor, descripcion, marca, proveedor, equivalencias FROM productos")
                for row in cursor.fetchall():
                    self.productos_db.append(dict(row))
            except sqlite3.OperationalError:
                pass
            conn.close()
        except sqlite3.OperationalError as e:
            print(f"Error al cargar DB en modo RO: {e}")

    def aplicar_reglas_markdown(self, texto, reglas):
        for r in reglas:
            accion = r.get("accion")
            patron = r.get("patron", "")
            reemplazo = r.get("reemplazo", "")

            if not patron: continue

            if accion == "borrar":
                texto = texto.replace(patron, "")
            elif accion == "separar":
                texto = texto.replace(patron, patron + " | ")
            elif accion == "reemplazar":
                texto = texto.replace(patron, reemplazo)
        return texto

    def _compactar_bloques(self, bloques):
        final_rows = []
        for b in bloques:
            # We assume b is a dict of lists per column
            codigos = [c for c in b.get("0", []) if str(c).strip()]
            amps = [c for c in b.get("1", []) if str(c).strip()]
            marcas = [c for c in b.get("2", []) if str(c).strip()]
            aplicaciones = [c for c in b.get("3", []) if str(c).strip()]
            precios = [c for c in b.get("9", []) if str(c).strip() and "$" in str(c)]

            max_len = max(len(codigos), len(precios))
            for i in range(max_len):
                cod = codigos[i] if i < len(codigos) else ""
                amp = amps[i] if i < len(amps) else ""
                marca = marcas[i] if i < len(marcas) else ""
                aplic = aplicaciones[i] if i < len(aplicaciones) else ""
                precio = precios[i] if i < len(precios) else ""

                # Expand application
                if not aplic and aplicaciones:
                    aplic = aplicaciones[0]

                final_rows.append([cod, amp, marca, aplic, precio])
        return final_rows

    def convertir_origen_a_markdown(self, filas_crudas, perfil=None):
        reglas = perfil.get("reglas_markdown", []) if perfil else []

        filas_procesadas = []
        for i, row in enumerate(filas_crudas):
            row_str = " ".join([str(c) for c in row if c])

            ignorar_fila = False
            for r in reglas:
                if r.get("accion") == "ignorar_fila" and r.get("patron") in row_str:
                    ignorar_fila = True
                    break

            if ignorar_fila: continue

            # Check intrusive dimensions
            if re.match(r"^\s*\d{3}\s+\d{3}\s+\d{3}\s*$", str(row[0]).strip()):
                continue
            if len(row) > 1 and re.match(r"^\s*\d{3}\s+\d{3}\s+\d{3}\s*$", str(row[1]).strip()):
                continue

            # Filter vehicle models directly in code column
            if re.match(r"^[a-zA-Z0-9,.-]+$", str(row[0]).strip()) and len(str(row[0]).split(',')) > 3:
                continue

            # Format to Markdown
            cols = []

            # Handle multi-line cells by flattening or taking the first valid
            # Actually, `obtener_previsualizacion_cruda` already flattened them if they are simple lists.
            # But the prompt mentions "Desfase de filas M40FD, M18FD". This implies grouping by blocks!

            # Let's extract the code, desc, brand, price manually
            cod = str(row[0]).strip()
            desc = str(row[1]).strip()
            marca = str(row[2]).strip() if len(row) > 2 else ""
            aplic = str(row[3]).strip() if len(row) > 3 else ""
            precio = str(row[-1]).strip() if len(row) > 4 else ""

            # Remove dimensions from brand
            marca = re.sub(r"\d{3}\s+\d{3}\s+\d{3}", "", marca).strip()

            # Split brand from application
            if " " in marca:
                parts = marca.split(" ", 1)
                marca = parts[0]
                if not aplic:
                    aplic = parts[1]
                else:
                    aplic = parts[1] + " " + aplic

            # Seineca specific logic
            if "\n" in precio and "$" in precio and not cod:
                p_parts = precio.split("\n")
                new_precio = ""
                equiv = ""
                for p in p_parts:
                    if "$" in p:
                        new_precio = p
                    else:
                        equiv = p
                precio = new_precio
                cod = equiv

            # Apply text replacements
            for col_val in [cod, desc, marca, aplic, precio]:
                col_val = self.aplicar_reglas_markdown(col_val, reglas)
                cols.append(col_val)

            filas_procesadas.append({
                "cod": cols[0],
                "desc": cols[1],
                "marca": cols[2],
                "aplic": cols[3],
                "precio": cols[4]
            })

        # Compact (Vertical Alignment)
        # Block is defined by an empty row or a new header.
        # For simplicity, we align the entire page array if it seems to have disjoint columns.
        codigos = [f["cod"] for f in filas_procesadas if f["cod"]]
        descs = [f["desc"] for f in filas_procesadas if f["desc"]]
        marcas = [f["marca"] for f in filas_procesadas if f["marca"]]
        aplics = [f["aplic"] for f in filas_procesadas if f["aplic"]]
        precios = [f["precio"] for f in filas_procesadas if f["precio"] and "$" in f["precio"]]

        max_len = max(len(codigos), len(precios))
        markdown = "| Fila | Col 0 [CÓDIGO] | Col 1 [DESC] | Col 2 [MARCA] | Col 3 [APLICACIÓN] | Col 9 [PRECIO] |\n|---|---|---|---|---|---|\n"

        for i in range(max_len):
            c0 = codigos[i] if i < len(codigos) else ""
            c1 = descs[i] if i < len(descs) else ""
            c2 = marcas[i] if i < len(marcas) else ""
            c3 = aplics[i] if i < len(aplics) else ""
            c9 = precios[i] if i < len(precios) else ""

            # Propagate application
            if not c3 and aplics:
                c3 = aplics[0]

            md_row = f"| {i+1} | {c0} | {c1} | {c2} | {c3} | {c9} |\n"
            markdown += md_row

        return markdown

    def _es_cabecera(self, row):
        txt = " ".join([str(c).upper() for c in row if c])
        keywords = ["CODIGO", "CÓDIGO", "DESCRIPCION", "DESCRIPCIÓN", "MARCA", "PRECIO", "COSTO", "FINAL", "AMP", "APLICACION"]
        return sum(1 for k in keywords if k in txt) >= 2

    def extraer_filas_inteligentes_pdf(self, page, modo_separacion="Automático Inteligente (Desglosado por renglón)"):
        if modo_separacion == "Por Coordenadas de Cabecera (Sin bordes)":
            words = page.extract_words(keep_blank_chars=False, x_tolerance=2, y_tolerance=2)
            if not words: return []
            words.sort(key=lambda w: (w['top'], w['x0']))
            rows_by_top = []
            current_row = []
            current_top = words[0]['top']
            for w in words:
                if abs(w['top'] - current_top) > 3:
                    if current_row: rows_by_top.append(current_row)
                    current_row = [w]
                    current_top = w['top']
                else:
                    current_row.append(w)
            if current_row: rows_by_top.append(current_row)

            header_row = None
            cortes_x = []
            for row in rows_by_top[:10]:
                txt = " ".join([w['text'].upper() for w in row])
                if sum(1 for k in ["CODIGO", "CÓDIGO", "DESCRIPCION", "MARCA", "PRECIO", "COSTO", "AMP", "APLICACION"] if k in txt) >= 2:
                    header_row = row
                    cortes_x = [w['x0'] for w in row]
                    break
            if not cortes_x:
                cortes_x = [0, 100, 200, 300, 400, 500]
            final_rows = []
            for row in rows_by_top:
                new_row = [""] * len(cortes_x)
                for w in row:
                    x0 = w['x0']
                    col_idx = 0
                    for i, cx in enumerate(cortes_x):
                        if x0 >= cx - 10: col_idx = i
                    new_row[col_idx] = (new_row[col_idx] + " " + w['text']).strip()
                final_rows.append(new_row)
            return final_rows

        tables = page.extract_tables()
        if not tables:
            text = page.extract_text()
            if not text: return []
            rows = []
            for line in text.split('\n'):
                rows.append(re.split(r'\s{2,}', line))
            return rows

        raw_rows = []
        for table in tables:
            for row in table:
                raw_rows.append([str(c) if c is not None else "" for c in row])

        final_rows = []
        last_aplicacion = ""

        for row in raw_rows:
            if not any(row): continue
            if self._es_cabecera(row):
                final_rows.append(row)
                continue

            aplic = ""
            for c in row:
                if len(str(c)) > 10 and not re.search(r'\d', str(c)) and " " in str(c):
                    aplic = str(c).strip()
            if aplic: last_aplicacion = aplic

            max_lines = 1
            split_cells = []
            for cell in row:
                parts = str(cell).split('\n')
                max_lines = max(max_lines, len(parts))
                split_cells.append(parts)

            for i in range(max_lines):
                new_row = []
                for parts in split_cells:
                    if i < len(parts): new_row.append(parts[i].strip())
                    else: new_row.append("")

                if new_row and new_row[0]:
                    match = re.search(r'\b(\d{1,2}\s*[xX]\s*\d{2,3}[A-Z]?)\b', new_row[0])
                    if match:
                        amp = match.group(1)
                        parts_cod = new_row[0].split(amp)
                        cod = parts_cod[0].strip()
                        marca = parts_cod[1].strip() if len(parts_cod) > 1 else ""
                        new_row[0] = cod
                        if len(new_row) > 1: new_row[1] = amp
                        else: new_row.append(amp)
                        if len(new_row) > 2: new_row[2] = marca
                        else: new_row.append(marca)

                if not any(len(str(c)) > 10 and " " in str(c) for c in new_row):
                    if len(new_row) > 3: new_row[3] = last_aplicacion
                    else:
                        while len(new_row) < 3: new_row.append("")
                        new_row.append(last_aplicacion)

                final_rows.append(new_row)

        cleaned_rows = []
        for i, row in enumerate(final_rows):
            if str(row[-1]).strip() == "$" and len(row) > 9:
                row[-1] = ""
            cleaned_rows.append(row)

        codes = [r for r in cleaned_rows if str(r[0]).strip() and str(r[0]).upper() not in ["CÓDIGO", "CODIGO", "ARTICULO"]]
        prices = [str(r[-1]).strip() for r in cleaned_rows if str(r[-1]).strip() and str(r[-1]).strip() != "$"]

        if len(codes) > 0 and len(codes) <= len(prices):
            p_idx = len(prices) - len(codes)
            for j, c in enumerate(codes):
                c[-1] = prices[p_idx + j]

        return [r for r in cleaned_rows if str(r[0]).strip()]

    def autodetectar_mapeo_columnas(self, filas):
        mapeo = {
            "fila_inicio": 1,
            "col_codigo": None,
            "col_descripcion": None,
            "col_marca": None,
            "col_precio": None,
            "cols_equivalencias": []
        }
        for i, fila in enumerate(filas[:15]):
            txt = " ".join([str(c).upper() for c in fila if c])
            if sum(1 for k in ["CODIGO", "CÓDIGO", "ARTICULO", "DESCRIPCION", "MARCA", "PRECIO", "COSTO", "FINAL", "AMP", "APLICACION"] if k in txt) >= 2:
                mapeo["fila_inicio"] = i + 1
                for j, c in enumerate(fila):
                    c_up = str(c).upper()
                    if "CODIGO" in c_up or "CÓDIGO" in c_up or "ARTICULO" in c_up or "COD" == c_up:
                        mapeo["col_codigo"] = j
                    elif "MARCA" in c_up or "FABRICANTE" in c_up:
                        mapeo["col_marca"] = j
                    elif "DESCRIPCION" in c_up or "DESCRIPCIÓN" in c_up or "APLICACION" in c_up or "APLICACIÓN" in c_up or "DETALLE" in c_up:
                        mapeo["col_descripcion"] = j
                    elif "PRECIO" in c_up or "COSTO" in c_up or "FINAL" in c_up:
                        mapeo["col_precio"] = j
                    elif "AMP" in c_up or "EQUIVALENCIA" in c_up or "MANN" in c_up or "FRAM" in c_up:
                        mapeo["cols_equivalencias"].append(j)
                break
        return mapeo

    def obtener_previsualizacion_cruda(self, ruta_archivo, gestor_perfiles=None, proveedor=None):
        _, ext = os.path.splitext(ruta_archivo.lower())
        preview = {}
        if ext in ['.xlsx', '.xls']:
            try:
                xls = pd.ExcelFile(ruta_archivo)
                for sheet_name in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet_name, nrows=100, header=None)
                    df = df.fillna("")
                    preview[sheet_name] = df.astype(str).values.tolist()
            except Exception as e:
                print(f"Error excel: {e}")
        elif ext == '.pdf':
            try:
                perfil_general = gestor_perfiles.obtener_perfil(proveedor, "PDF", "GENERAL") if gestor_perfiles and proveedor else {}
                modo = perfil_general.get("modo_lectura_pdf", "Automático Inteligente (Desglosado por renglón)")

                with pdfplumber.open(ruta_archivo) as pdf:
                    for i, page in enumerate(pdf.pages):
                        if i >= 60: break
                        if modo == "Tablas Crudas Originales":
                            tables = page.extract_tables()
                            rows = []
                            if tables:
                                for table in tables:
                                    for row in table:
                                        rows.append([str(c) if c is not None else "" for c in row])
                            else:
                                text = page.extract_text()
                                if text:
                                    for line in text.split('\n'):
                                        rows.append(re.split(r'\s{2,}', line))
                            preview[f"Página {i+1}"] = rows[:100]
                        else:
                            preview[f"Página {i+1}"] = self.extraer_filas_inteligentes_pdf(page, modo_separacion=modo)[:100]
            except Exception as e:
                print(f"Error pdf: {e}")
        return preview

    def parsear_desde_markdown(self, markdown_text):
        productos = []
        lines = markdown_text.strip().split('\n')
        for line in lines:
            if not line.strip() or line.strip().startswith('|---'): continue
            if 'Fila' in line and 'CÓDIGO' in line: continue

            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 7:
                # | row_idx | cod | desc | marca | aplic | precio |
                cod = parts[2]
                desc = parts[3]
                marca = parts[4]
                aplic = parts[5]
                precio_str = parts[6]

                desc_final = desc + " " + aplic if aplic else desc
                costo = limpiar_precio_argentino(precio_str)

                if "$" in cod or cod in ["175", "190", "205", "240", "275"]: continue
                if costo <= 0: continue
                if not cod or not desc_final: continue

                productos.append({
                    "codigo_proveedor": cod,
                    "descripcion": desc_final.strip(),
                    "costo": costo,
                    "marca": marca,
                    "equivalencias": "",
                    "origen": "MARKDOWN"
                })
        return productos

    def extraer_productos_con_perfil(self, ruta_archivo, proveedor, gestor_perfiles, modo_precio_baterias=False, hojas_seleccionadas_ui=None, callback_progreso=None):
        _, ext = os.path.splitext(ruta_archivo.lower())
        productos = []
        if ext in ['.xlsx', '.xls']:
            try:
                xls = pd.ExcelFile(ruta_archivo)
                hojas = hojas_seleccionadas_ui if hojas_seleccionadas_ui else xls.sheet_names
                total_hojas = len(hojas)
                for i, sheet_name in enumerate(hojas):
                    if callback_progreso: callback_progreso(i / total_hojas)
                    df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                    df = df.fillna("")
                    filas = df.astype(str).values.tolist()
                    perfil = gestor_perfiles.obtener_perfil(proveedor, "EXCEL", sheet_name)
                    if not perfil.get("activa", True):
                        continue
                    md = self.convertir_origen_a_markdown(filas, perfil)
                    productos.extend(self.parsear_desde_markdown(md))
            except Exception as e:
                print(e)
        elif ext == '.pdf':
            try:
                perfil_general = gestor_perfiles.obtener_perfil(proveedor, "PDF", "GENERAL")
                paginas_ignoradas = set(gestor_perfiles.obtener_metadatos_pdf(proveedor))
                modo = perfil_general.get("modo_lectura_pdf", "Automático Inteligente (Desglosado por renglón)")

                with pdfplumber.open(ruta_archivo) as pdf:
                    total_paginas = len(pdf.pages)
                    for i, page in enumerate(pdf.pages):
                        if callback_progreso: callback_progreso(i / total_paginas)
                        page_num = i + 1
                        if page_num in paginas_ignoradas or page_num in perfil_general.get("paginas_ignoradas", []):
                            continue

                        if modo == "Tablas Crudas Originales":
                            tables = page.extract_tables()
                            rows = []
                            if tables:
                                for table in tables:
                                    for row in table:
                                        rows.append([str(c) if c is not None else "" for c in row])
                            else:
                                text = page.extract_text()
                                if text:
                                    for line in text.split('\n'):
                                        rows.append(re.split(r'\s{2,}', line))
                        else:
                            rows = self.extraer_filas_inteligentes_pdf(page, modo_separacion=modo)

                        md = self.convertir_origen_a_markdown(rows, perfil_general)
                        productos.extend(self.parsear_desde_markdown(md))
            except Exception as e:
                print(e)

        if callback_progreso: callback_progreso(1.0)
        return productos

    def cruzar_productos(self, productos_extraidos, proveedor):
        nuevos = []
        actualizaciones = []
        mapa_prov = {}
        for p in self.productos_db:
            if str(p.get("proveedor", "")).upper() == proveedor.upper():
                cod = str(p.get("codigo_proveedor", "")).strip().upper()
                mapa_prov[cod] = p

        for prod in productos_extraidos:
            cod_extraido = str(prod["codigo_proveedor"]).strip().upper()
            es_corto_o_num = len(cod_extraido) < 5 or cod_extraido.isdigit()

            if cod_extraido in mapa_prov:
                db_prod = mapa_prov[cod_extraido]
                if es_corto_o_num:
                    desc_db = str(db_prod.get("descripcion", "")).upper()
                    desc_ext = prod["descripcion"].upper()
                    palabras_ext = set(desc_ext.split())
                    palabras_db = set(desc_db.split())
                    if not palabras_ext.intersection(palabras_db):
                        nuevos.append(prod)
                        continue
                actualizaciones.append({**prod, "id_db": db_prod.get("id")})
            else:
                nuevos.append(prod)
        return nuevos, actualizaciones

class ModalEntrenadorPrevisualizacion(ctk.CTkToplevel):
    def __init__(self, master, ruta_archivo, proveedor, gestor_perfiles, callback_guardar):
        super().__init__(master)
        self.title("👁️ Previsualizar y Entrenar Markdown")
        self.geometry("1100x700")
        self.minsize(1000, 600)
        self.ruta_archivo = ruta_archivo
        self.proveedor = proveedor
        self.gestor_perfiles = gestor_perfiles
        self.callback_guardar = callback_guardar
        self.motor = MotorCruceBarterPlus()
        self.preview_data = {}
        self.origen_actual = ""
        _, self.ext = os.path.splitext(self.ruta_archivo.lower())
        self.tipo_archivo = "EXCEL" if self.ext in [".xlsx", ".xls"] else "PDF"

        self.crear_ui()
        self.cargar_datos()

    def crear_ui(self):
        # Top Bar
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(top_frame, text="Origen:").pack(side="left", padx=5)
        self.cmb_origen = ctk.CTkComboBox(top_frame, values=[], command=self.on_origen_change)
        self.cmb_origen.pack(side="left", padx=5)

        self.var_activa = tk.BooleanVar(value=True)
        self.chk_activa = ctk.CTkCheckBox(top_frame, text="✅ Lista Válida", variable=self.var_activa, command=self.on_activa_change)
        self.chk_activa.pack(side="left", padx=20)

        if self.tipo_archivo == "PDF":
            ctk.CTkLabel(top_frame, text="Ignorar Págs (ej: 1, 5-7):").pack(side="left", padx=5)
            self.ent_paginas_ign = ctk.CTkEntry(top_frame, width=80)
            self.ent_paginas_ign.pack(side="left", padx=5)
            self.ent_paginas_ign.bind("<FocusOut>", self.on_paginas_ign_change)

        btn_guardar_top = ctk.CTkButton(top_frame, text="💾 Guardar Entrenamiento y Extraer desde Markdown", fg_color="green", hover_color="darkgreen", command=self.guardar_y_extraer)
        btn_guardar_top.pack(side="right", padx=10)

        # Main Layout
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Split Panels
        main_frame.rowconfigure(0, weight=6) # Markdown Editor
        main_frame.rowconfigure(1, weight=1) # Training Bar
        main_frame.rowconfigure(2, weight=3) # Live Preview
        main_frame.columnconfigure(0, weight=1)

        # 1. Markdown Editor
        frame_md = ctk.CTkFrame(main_frame)
        frame_md.grid(row=0, column=0, sticky="nsew", pady=2)
        ctk.CTkLabel(frame_md, text="Editor Markdown Interactivo (Edita en vivo):").pack(anchor="w", padx=5)

        self.txt_markdown = ctk.CTkTextbox(frame_md, font=("Consolas", 12), wrap="none")
        self.txt_markdown.pack(fill="both", expand=True, padx=5, pady=5)
        self.txt_markdown.bind("<KeyRelease>", lambda e: self.actualizar_live_preview())

        # 2. Training Bar
        frame_train = ctk.CTkFrame(main_frame)
        frame_train.grid(row=1, column=0, sticky="nsew", pady=2)
        ctk.CTkLabel(frame_train, text="Enseñar Regla al Convertidor Markdown:").pack(side="left", padx=5)

        self.ent_patron = ctk.CTkEntry(frame_train, width=200, placeholder_text="Texto/Patrón mal tomado...")
        self.ent_patron.pack(side="left", padx=5)

        self.cmb_accion = ctk.CTkComboBox(frame_train, values=[
            "🗑️ Borrar este texto/medida siempre",
            "✂️ Separar en Marca | Descripción",
            "⬆️ Ignorar fila completa",
            "🔄 Reemplazar por ->"
        ], width=250)
        self.cmb_accion.pack(side="left", padx=5)

        self.ent_reemplazo = ctk.CTkEntry(frame_train, width=150, placeholder_text="Texto de reemplazo...")
        self.ent_reemplazo.pack(side="left", padx=5)

        btn_enseñar = ctk.CTkButton(frame_train, text="🧠 Enseñar Regla", command=self.enseñar_regla)
        btn_enseñar.pack(side="left", padx=10)

        # 3. Live Preview Table
        frame_preview = ctk.CTkFrame(main_frame)
        frame_preview.grid(row=2, column=0, sticky="nsew", pady=2)

        top_preview = ctk.CTkFrame(frame_preview)
        top_preview.pack(fill="x")
        ctk.CTkLabel(top_preview, text="Vista Previa de Productos Aprendidos:").pack(side="left", padx=5)
        ctk.CTkButton(top_preview, text="🔄 Actualizar Vista Previa desde el Markdown", command=self.actualizar_live_preview).pack(side="right", padx=5)

        self.tree_live = ttk.Treeview(frame_preview, columns=("Codigo", "Descripcion", "Marca", "Costo", "Estado"), show="headings")
        self.tree_live.heading("Codigo", text="Código")
        self.tree_live.heading("Descripcion", text="Descripción Final Armada")
        self.tree_live.heading("Marca", text="Marca")
        self.tree_live.heading("Costo", text="$ Costo")
        self.tree_live.heading("Estado", text="Estado Validación")
        self.tree_live.pack(fill="both", expand=True, padx=5, pady=5)
        scroll_y2 = ttk.Scrollbar(frame_preview, orient="vertical", command=self.tree_live.yview)
        scroll_y2.pack(side="right", fill="y")
        self.tree_live.configure(yscrollcommand=scroll_y2.set)

        # Bottom Bar
        bottom_frame = ctk.CTkFrame(self, height=50)
        bottom_frame.pack(side="bottom", fill="x", padx=10, pady=10)
        self.lbl_prueba = ctk.CTkLabel(bottom_frame, text="")
        self.lbl_prueba.pack(side="left", padx=10)
        btn_guardar_bot = ctk.CTkButton(bottom_frame, text="💾 Guardar Entrenamiento y Extraer desde Markdown", fg_color="green", hover_color="darkgreen", command=self.guardar_y_extraer)
        btn_guardar_bot.pack(side="right", padx=5)

    def cargar_datos(self):
        self.preview_data = self.motor.obtener_previsualizacion_cruda(self.ruta_archivo, self.gestor_perfiles, self.proveedor)
        origenes = list(self.preview_data.keys())
        if origenes:
            self.cmb_origen.configure(values=origenes)
            self.cmb_origen.set(origenes[0])
            self.on_origen_change(origenes[0])

        if self.tipo_archivo == "PDF":
            pags = self.gestor_perfiles.obtener_metadatos_pdf(self.proveedor)
            self.ent_paginas_ign.delete(0, tk.END)
            self.ent_paginas_ign.insert(0, ",".join(map(str, pags)))

    def on_origen_change(self, origen):
        self.origen_actual = origen
        ident = "GENERAL" if self.tipo_archivo == "PDF" else origen
        perfil = self.gestor_perfiles.obtener_perfil(self.proveedor, self.tipo_archivo, ident)

        if self.tipo_archivo == "EXCEL":
            hojas = self.gestor_perfiles.obtener_metadatos_excel(self.proveedor)
            self.var_activa.set(origen in hojas if hojas else perfil.get("activa", True))
        else:
            pags_ign = self.gestor_perfiles.obtener_metadatos_pdf(self.proveedor)
            try: num = int(origen.replace("Página ", ""))
            except: num = -1
            self.var_activa.set(num not in pags_ign)

        self.cargar_markdown()

    def on_activa_change(self):
        if self.tipo_archivo == "PDF":
            try: num = int(self.origen_actual.replace("Página ", ""))
            except: return
            pags = self.gestor_perfiles.obtener_metadatos_pdf(self.proveedor)
            if not self.var_activa.get():
                if num not in pags: pags.append(num)
            else:
                if num in pags: pags.remove(num)
            self.gestor_perfiles.actualizar_metadatos_pdf(self.proveedor, pags)
            self.ent_paginas_ign.delete(0, tk.END)
            self.ent_paginas_ign.insert(0, ",".join(map(str, pags)))

    def on_paginas_ign_change(self, event=None):
        txt = self.ent_paginas_ign.get()
        pags = []
        for p in txt.split(','):
            p = p.strip()
            if not p: continue
            if '-' in p:
                try:
                    start, end = map(int, p.split('-'))
                    pags.extend(range(start, end+1))
                except: pass
            else:
                try: pags.append(int(p))
                except: pass
        self.gestor_perfiles.actualizar_metadatos_pdf(self.proveedor, list(set(pags)))
        self.on_origen_change(self.origen_actual)

    def cargar_markdown(self):
        ident = "GENERAL" if self.tipo_archivo == "PDF" else self.origen_actual
        perfil = self.gestor_perfiles.obtener_perfil(self.proveedor, self.tipo_archivo, ident)
        filas = self.preview_data.get(self.origen_actual, [])

        md = self.motor.convertir_origen_a_markdown(filas, perfil)
        self.txt_markdown.delete("1.0", tk.END)
        self.txt_markdown.insert(tk.END, md)
        self.actualizar_live_preview()

    def enseñar_regla(self):
        patron = self.ent_patron.get().strip()
        if not patron: return
        accion_txt = self.cmb_accion.get()
        reemplazo = self.ent_reemplazo.get().strip()

        accion = "borrar"
        if "Separar" in accion_txt: accion = "separar"
        elif "Ignorar" in accion_txt: accion = "ignorar_fila"
        elif "Reemplazar" in accion_txt: accion = "reemplazar"

        ident = "GENERAL" if self.tipo_archivo == "PDF" else self.origen_actual
        perfil = self.gestor_perfiles.obtener_perfil(self.proveedor, self.tipo_archivo, ident)

        if "reglas_markdown" not in perfil:
            perfil["reglas_markdown"] = []

        perfil["reglas_markdown"].append({
            "accion": accion,
            "patron": patron,
            "reemplazo": reemplazo
        })

        self.gestor_perfiles.guardar_perfil(self.proveedor, self.tipo_archivo, ident, perfil)
        self.cargar_markdown()

    def actualizar_live_preview(self):
        md = self.txt_markdown.get("1.0", tk.END)
        prods = self.motor.parsear_desde_markdown(md)

        self.tree_live.delete(*self.tree_live.get_children())

        if not prods:
            self.lbl_prueba.configure(text="No se detectaron productos válidos.", text_color="red")
        else:
            self.lbl_prueba.configure(text=f"Detectados {len(prods)} productos válidos.", text_color="green")
            for p in prods[:50]:
                estado = "✅ Ok"
                self.tree_live.insert("", "end", values=(
                    p['codigo_proveedor'],
                    p['descripcion'],
                    p['marca'],
                    f"$ {p['costo']}",
                    estado
                ))

    def guardar_y_extraer(self):
        # Already saved via enseñar_regla or live edits don't persist code structure natively
        # But we will trigger the main app extraction
        self.callback_guardar()
        self.destroy()


class UnificadorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BarterPlus Unificador de Listas - Motor Local 100%")
        self.geometry("1200x800")

        self.gestor_perfiles = GestorPerfilesEntrenamiento()
        self.motor = MotorCruceBarterPlus()

        self.ruta_archivo = ""
        self.productos_extraidos = []

        self.crear_ui()

    def crear_ui(self):
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(header, text="BarterPlus Unificador", font=("Arial", 20, "bold")).pack(side="left", padx=10)
        self.lbl_db_estado = ctk.CTkLabel(header, text="Base: barterplus.db (Solo Lectura)", text_color="green")
        self.lbl_db_estado.pack(side="left", padx=20)
        self.lbl_perfiles = ctk.CTkLabel(header, text=f"🧠 Perfiles Entrenados: {len(self.gestor_perfiles.perfiles)}")
        self.lbl_perfiles.pack(side="right", padx=10)

        panel_carga = ctk.CTkFrame(self)
        panel_carga.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(panel_carga, text="Proveedor:").pack(side="left", padx=5)
        self.ent_proveedor = ctk.CTkEntry(panel_carga, width=200)
        self.ent_proveedor.pack(side="left", padx=5)

        self.lbl_estado_perfil = ctk.CTkLabel(panel_carga, text="⚪ Sin perfil")
        self.lbl_estado_perfil.pack(side="left", padx=10)
        self.ent_proveedor.bind("<KeyRelease>", self.verificar_perfil_proveedor)

        ctk.CTkButton(panel_carga, text="📂 Seleccionar Lista (Excel o PDF)", command=self.seleccionar_archivo).pack(side="left", padx=20)

        self.btn_previsualizar = ctk.CTkButton(panel_carga, text="👁️ Previsualizar y Entrenar Columnas", fg_color="orange", hover_color="darkorange", state="disabled", command=self.abrir_entrenador)
        self.btn_previsualizar.pack(side="left", padx=5)

        self.btn_analizar = ctk.CTkButton(panel_carga, text="⚡ Analizar y Extraer Lista", fg_color="green", hover_color="darkgreen", state="disabled", command=self.analizar_lista)
        self.btn_analizar.pack(side="left", padx=5)

        self.lbl_archivo = ctk.CTkLabel(panel_carga, text="Ningún archivo seleccionado.")
        self.lbl_archivo.pack(side="left", padx=10)

        self.progress = ctk.CTkProgressBar(self)
        self.progress.pack(fill="x", padx=10, pady=5)
        self.progress.set(0)

        self.panel_hojas = ctk.CTkFrame(self)

        panel_auditoria = ctk.CTkFrame(self)
        panel_auditoria.pack(fill="both", expand=True, padx=10, pady=5)

        top_auditoria = ctk.CTkFrame(panel_auditoria)
        top_auditoria.pack(fill="x", padx=5, pady=5)

        self.btn_actualizaciones = ctk.CTkButton(top_auditoria, text="🔄 Actualizaciones de Precio (0)", command=lambda: self.mostrar_auditoria("ACTUALIZACIONES"))
        self.btn_actualizaciones.pack(side="left", padx=5)

        self.btn_nuevos = ctk.CTkButton(top_auditoria, text="✨ Productos Nuevos (0)", command=lambda: self.mostrar_auditoria("NUEVOS"))
        self.btn_nuevos.pack(side="left", padx=5)

        self.ent_buscar = ctk.CTkEntry(top_auditoria, width=300, placeholder_text="🔍 Filtrar por código, marca o descripción...")
        self.ent_buscar.pack(side="right", padx=5)
        self.ent_buscar.bind("<KeyRelease>", self.filtrar_auditoria)

        self.tree_auditoria = ttk.Treeview(panel_auditoria, columns=("Origen", "Codigo", "Descripcion", "Marca", "Costo", "Equivalencias"), show="headings")
        self.tree_auditoria.heading("Origen", text="Origen")
        self.tree_auditoria.heading("Codigo", text="Código")
        self.tree_auditoria.heading("Descripcion", text="Descripción")
        self.tree_auditoria.heading("Marca", text="Marca")
        self.tree_auditoria.heading("Costo", text="Costo")
        self.tree_auditoria.heading("Equivalencias", text="Equivalencias")
        self.tree_auditoria.pack(fill="both", expand=True, padx=5, pady=5)

        scroll_y = ttk.Scrollbar(panel_auditoria, orient="vertical", command=self.tree_auditoria.yview)
        scroll_y.pack(side="right", fill="y")
        self.tree_auditoria.configure(yscrollcommand=scroll_y.set)

        ctk.CTkButton(self, text="💾 Exportar Excel Unificado (.xlsx)", command=self.exportar_excel).pack(pady=10)

        self.datos_actuales = []

    def verificar_perfil_proveedor(self, event=None):
        prov = self.ent_proveedor.get().strip().upper()
        if not prov:
            self.lbl_estado_perfil.configure(text="⚪ Sin perfil")
            return

        tipo = "EXCEL" if self.ruta_archivo and self.ruta_archivo.endswith((".xls", ".xlsx")) else "PDF"
        clave = f"{prov}::{tipo}::"
        encontrado = any(k.startswith(clave) for k in self.gestor_perfiles.perfiles.keys())

        if encontrado:
            self.lbl_estado_perfil.configure(text="✅ Proveedor con perfil entrenado", text_color="green")
        else:
            self.lbl_estado_perfil.configure(text="⚪ Sin perfil (usará automático)", text_color="gray")

    def seleccionar_archivo(self):
        ruta = filedialog.askopenfilename(filetypes=[("Listas", "*.xlsx *.xls *.pdf")])
        if ruta:
            self.ruta_archivo = ruta
            self.lbl_archivo.configure(text=os.path.basename(ruta))
            self.btn_previsualizar.configure(state="normal")
            self.btn_analizar.configure(state="normal")
            self.verificar_perfil_proveedor()

            _, ext = os.path.splitext(self.ruta_archivo.lower())
            if ext in [".xls", ".xlsx"]:
                self.mostrar_panel_hojas()
            else:
                self.panel_hojas.pack_forget()

    def mostrar_panel_hojas(self):
        for widget in self.panel_hojas.winfo_children():
            widget.destroy()
        self.panel_hojas.pack(fill="x", padx=10, pady=5, after=self.progress)

        try:
            xls = pd.ExcelFile(self.ruta_archivo)
            prov = self.ent_proveedor.get().strip().upper()
            hojas_activas = self.gestor_perfiles.obtener_metadatos_excel(prov)

            ctk.CTkLabel(self.panel_hojas, text="Hojas a procesar:").pack(side="left", padx=5)
            self.vars_hojas = {}
            for sheet in xls.sheet_names:
                var = tk.BooleanVar(value=(sheet in hojas_activas) if hojas_activas else True)
                self.vars_hojas[sheet] = var
                chk = ctk.CTkCheckBox(self.panel_hojas, text=sheet, variable=var)
                chk.pack(side="left", padx=5)
        except Exception as e:
            print(f"Error cargando hojas: {e}")

    def abrir_entrenador(self):
        prov = self.ent_proveedor.get().strip()
        if not prov:
            messagebox.showwarning("Aviso", "Debe ingresar un nombre de proveedor.")
            return

        ModalEntrenadorPrevisualizacion(self, self.ruta_archivo, prov, self.gestor_perfiles, self.on_entrenador_guardado)

    def on_entrenador_guardado(self):
        self.lbl_perfiles.configure(text=f"🧠 Perfiles Entrenados: {len(self.gestor_perfiles.perfiles)}")
        self.verificar_perfil_proveedor()
        self.analizar_lista()

    def analizar_lista(self):
        prov = self.ent_proveedor.get().strip()
        if not prov:
            messagebox.showwarning("Aviso", "Debe ingresar un nombre de proveedor.")
            return

        def cb_progreso(val):
            self.progress.set(val)
            self.update_idletasks()

        def worker():
            hojas_sel = None
            if hasattr(self, 'vars_hojas'):
                hojas_sel = [h for h, v in self.vars_hojas.items() if v.get()]

            self.btn_analizar.configure(state="disabled")
            try:
                productos = self.motor.extraer_productos_con_perfil(
                    self.ruta_archivo,
                    prov,
                    self.gestor_perfiles,
                    hojas_seleccionadas_ui=hojas_sel,
                    callback_progreso=cb_progreso
                )

                self.nuevos, self.actualizaciones = self.motor.cruzar_productos(productos, prov)

                self.after(0, self.finalizar_analisis)
            except Exception as e:
                traceback.print_exc()
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.after(0, lambda: self.btn_analizar.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def finalizar_analisis(self):
        self.btn_actualizaciones.configure(text=f"🔄 Actualizaciones de Precio ({len(self.actualizaciones)})")
        self.btn_nuevos.configure(text=f"✨ Productos Nuevos ({len(self.nuevos)})")
        self.mostrar_auditoria("NUEVOS")

    def mostrar_auditoria(self, tipo):
        self.tree_auditoria.delete(*self.tree_auditoria.get_children())
        if tipo == "NUEVOS":
            self.datos_actuales = self.nuevos
        else:
            self.datos_actuales = self.actualizaciones

        self.filtrar_auditoria()

    def filtrar_auditoria(self, event=None):
        self.tree_auditoria.delete(*self.tree_auditoria.get_children())
        term = self.ent_buscar.get().lower()

        for p in self.datos_actuales:
            if term in p['codigo_proveedor'].lower() or term in p['descripcion'].lower() or term in str(p['marca']).lower():
                self.tree_auditoria.insert("", "end", values=(
                    p.get('origen', ''),
                    p['codigo_proveedor'],
                    p['descripcion'],
                    p['marca'],
                    p['costo'],
                    p['equivalencias']
                ))

    def exportar_excel(self):
        if not self.datos_actuales:
            messagebox.showinfo("Aviso", "No hay datos para exportar.")
            return

        ruta = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if ruta:
            try:
                df = pd.DataFrame(self.datos_actuales)
                df.to_excel(ruta, index=False)
                messagebox.showinfo("Éxito", f"Exportado a {ruta}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    app = UnificadorApp()
    app.mainloop()
