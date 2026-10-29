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
            "modo_lectura_pdf": "Automático Inteligente (Desglosado por renglón)",
            "nombres_cabecera_aprendidos": {}
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
                            # Use new intelligent engine
                            preview[f"Página {i+1}"] = self.extraer_filas_inteligentes_pdf(page, modo_separacion=modo)[:100]
            except Exception as e:
                print(f"Error pdf: {e}")
        return preview

    def _es_cabecera(self, row):
        txt = " ".join([str(c).upper() for c in row if c])
        keywords = ["CODIGO", "CÓDIGO", "DESCRIPCION", "DESCRIPCIÓN", "MARCA", "PRECIO", "COSTO", "FINAL", "AMP", "APLICACION"]
        return sum(1 for k in keywords if k in txt) >= 2

    def extraer_filas_inteligentes_pdf(self, page, modo_separacion="Automático Inteligente (Desglosado por renglón)"):
        # Strategy 1: Coordinates
        if modo_separacion == "Por Coordenadas de Cabecera (Sin bordes)":
            words = page.extract_words(keep_blank_chars=False, x_tolerance=2, y_tolerance=2)
            if not words: return []

            # Find rows
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

            # Find header
            header_row = None
            cortes_x = []
            for row in rows_by_top[:10]:
                txt = " ".join([w['text'].upper() for w in row])
                if sum(1 for k in ["CODIGO", "CÓDIGO", "DESCRIPCION", "MARCA", "PRECIO", "COSTO", "AMP", "APLICACION"] if k in txt) >= 2:
                    header_row = row
                    cortes_x = [w['x0'] for w in row]
                    break

            if not cortes_x:
                cortes_x = [0, 100, 200, 300, 400, 500] # Fallback

            final_rows = []
            for row in rows_by_top:
                new_row = [""] * len(cortes_x)
                for w in row:
                    x0 = w['x0']
                    col_idx = 0
                    for i, cx in enumerate(cortes_x):
                        if x0 >= cx - 10:
                            col_idx = i
                    new_row[col_idx] = (new_row[col_idx] + " " + w['text']).strip()
                final_rows.append(new_row)
            return final_rows

        # Strategy 2: Auto Desglosado (default)
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

        # Analyze if we have the Casa Baterias collapse problem
        header_len = 0
        for r in raw_rows[:10]:
            if self._es_cabecera(r):
                header_len = len([c for c in r if c])
                break

        final_rows = []
        # Propagation variables
        last_aplicacion = ""

        for row in raw_rows:
            if not any(row): continue

            if self._es_cabecera(row):
                final_rows.append(row)
                continue

            # Check if it's collapsed into col 0
            if len([c for c in row if c]) == 1 and "\n" in row[0]:
                pass # Proceed to multi-line expansion

            # Find application column (heuristics)
            aplic = ""
            for c in row:
                if len(str(c)) > 10 and not re.search(r'\d', str(c)) and " " in str(c):
                    aplic = str(c).strip()
            if aplic:
                last_aplicacion = aplic

            # Expand multiline
            max_lines = 1
            split_cells = []
            for cell in row:
                parts = str(cell).split('\n')
                max_lines = max(max_lines, len(parts))
                split_cells.append(parts)

            for i in range(max_lines):
                new_row = []
                for parts in split_cells:
                    if i < len(parts):
                        new_row.append(parts[i].strip())
                    else:
                        new_row.append("")


                # Casa Baterias pattern: DL 450 12X50 LEMOM
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
                    if len(new_row) > 3:
                        new_row[3] = last_aplicacion
                    else:
                        while len(new_row) < 3: new_row.append("")
                        new_row.append(last_aplicacion)

                final_rows.append(new_row)

        # Post-process to remove orphan dollars and align with Casa Baterias
        # 0: DL, 9: $
        # 1: UB, 9: $ 105
        # 2: "", 9: $ 113
        # We need to shift prices up if the first was just $
        cleaned_rows = []
        for i, row in enumerate(final_rows):
            if str(row[-1]).strip() == "$" and len(row) > 9:
                row[-1] = ""
            if not str(row[0]).strip() and str(row[-1]).strip() != "":
                # Orphan price without code, try to shift it up to previous valid code if it doesn't have a price
                # Or wait, Casa Baterias:
                # Row 0: DL 450 ... $ 90.000 ... $
                # Row 1: UB 670 ... $ 100.000 ... $ 105.361
                # Row 2: "" ... 15.000 ... $ 113.873
                # We need to assign prices properly.
                # Actually simpler: If code is valid, and next row is orphan price, take that price.
                pass
            cleaned_rows.append(row)

        # Let's do a smart realignment for Casa Baterias
        # If we have 2 codes but 3 prices ($, $ 105, $ 113), the valid prices are the last 2.
        # So assign them to the 2 codes.
        codes = [r for r in cleaned_rows if str(r[0]).strip() and r[0].upper() not in ["CÓDIGO", "CODIGO", "ARTICULO"]]
        prices = [str(r[-1]).strip() for r in cleaned_rows if str(r[-1]).strip() and str(r[-1]).strip() != "$"]

        if len(codes) > 0 and len(codes) <= len(prices):
            p_idx = len(prices) - len(codes)
            for j, c in enumerate(codes):
                c[-1] = prices[p_idx + j]

        # To avoid duplicating header if it was processed, return cleaned_rows directly since codes are references to cleaned_rows elements!
        # wait, we need to return the cleaned rows that have codes
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
                    prods = self._procesar_filas(filas, perfil, sheet_name)
                    productos.extend(prods)
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

                        prods = self._procesar_filas(rows, perfil_general, f"Página {page_num}")
                        productos.extend(prods)
            except Exception as e:
                print(e)

        if callback_progreso: callback_progreso(1.0)
        return productos

    def _procesar_filas(self, filas, perfil, origen):
        productos = []
        fila_inicio = int(perfil.get("fila_inicio", 1))
        filas_pie = int(perfil.get("filas_pie_ignorar", 0))
        modo_baterias = perfil.get("modo_multiline_baterias", False)

        col_codigo = perfil.get("col_codigo")
        col_descripcion = perfil.get("col_descripcion")
        col_precio = perfil.get("col_precio")
        col_marca = perfil.get("col_marca")
        cols_equiv = perfil.get("cols_equivalencias", [])
        marca_fija = perfil.get("marca_fija", "")

        filas_reales = filas[fila_inicio:] if fila_inicio < len(filas) else []
        if filas_pie > 0 and len(filas_reales) > filas_pie:
            filas_reales = filas_reales[:-filas_pie]

        filas_procesar = filas_reales # El _expand ya se hizo inteligentemente, pero mantenemos por si acaso

        for fila in filas_procesar:
            if not fila: continue

            def safe_get(idx):
                if idx is not None and isinstance(idx, int) and 0 <= idx < len(fila):
                    return str(fila[idx]).strip()
                return ""

            codigo = safe_get(col_codigo)
            desc = safe_get(col_descripcion)
            precio_str = safe_get(col_precio)
            marca = safe_get(col_marca) if col_marca is not None else marca_fija

            equivs = [safe_get(c) for c in cols_equiv]
            equivs = [e for e in equivs if e]

            if "\n" in precio_str and "$" in precio_str:
                parts = precio_str.split('\n')
                new_precio = ""
                for p in parts:
                    if "$" in p:
                        new_precio = p
                    elif p.strip():
                        equivs.append(p.strip())
                if not codigo and equivs:
                    codigo = equivs.pop(0)
                precio_str = new_precio

            if desc and equivs:
                desc = desc + " " + " ".join(equivs)

            costo = limpiar_precio_argentino(precio_str)

            if "$" in codigo: continue
            if codigo in ["175", "190", "205", "240", "275"]: continue
            if costo <= 0: continue
            if not codigo or not desc: continue

            productos.append({
                "codigo_proveedor": codigo,
                "descripcion": desc,
                "costo": costo,
                "marca": marca,
                "equivalencias": " | ".join(equivs) if equivs else "",
                "origen": origen
            })

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
        self.title("👁️ Previsualizar y Entrenar Columnas")
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

        if self.tipo_archivo == "PDF":
            ctk.CTkLabel(top_frame, text="Modo de Lectura:").pack(side="left", padx=10)
            self.cmb_modo = ctk.CTkComboBox(top_frame, values=[
                "Automático Inteligente (Desglosado por renglón)",
                "Por Coordenadas de Cabecera (Sin bordes)",
                "Tablas Crudas Originales"
            ], width=350, command=self.on_modo_change)
            self.cmb_modo.pack(side="left", padx=5)

        self.var_activa = tk.BooleanVar(value=True)
        self.chk_activa = ctk.CTkCheckBox(top_frame, text="✅ Lista Válida", variable=self.var_activa, command=self.on_activa_change)
        self.chk_activa.pack(side="left", padx=20)

        if self.tipo_archivo == "PDF":
            ctk.CTkLabel(top_frame, text="Ignorar Págs (ej: 1, 5-7):").pack(side="left", padx=5)
            self.ent_paginas_ign = ctk.CTkEntry(top_frame, width=80)
            self.ent_paginas_ign.pack(side="left", padx=5)
            self.ent_paginas_ign.bind("<FocusOut>", self.on_paginas_ign_change)

        ctk.CTkButton(top_frame, text="✨ Autodetectar Columnas", command=self.autodetectar).pack(side="right", padx=10)

        # Main Layout
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Left Panel (Training)
        left_panel = ctk.CTkFrame(main_frame, width=250)
        left_panel.pack(side="left", fill="y", padx=5, pady=5)

        def crear_combo(parent, label_text):
            ctk.CTkLabel(parent, text=label_text).pack(anchor="w", padx=5, pady=(2,0))
            cmb = ctk.CTkComboBox(parent, values=["Ninguna"] + [f"{i}" for i in range(25)])
            cmb.pack(fill="x", padx=5, pady=2)
            cmb.set("Ninguna")
            return cmb

        self.cmb_col_cod = crear_combo(left_panel, "Columna Código:")
        self.cmb_col_desc = crear_combo(left_panel, "Columna Descripción:")
        self.cmb_col_precio = crear_combo(left_panel, "Columna Precio / Costo:")
        self.cmb_col_marca = crear_combo(left_panel, "Columna Marca:")

        ctk.CTkLabel(left_panel, text="Columnas Equivalencias:").pack(anchor="w", padx=5, pady=(2,0))
        self.ent_cols_equiv = ctk.CTkEntry(left_panel)
        self.ent_cols_equiv.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(left_panel, text="Fila inicio datos:").pack(anchor="w", padx=5, pady=(2,0))
        self.ent_fila_inicio = ctk.CTkEntry(left_panel)
        self.ent_fila_inicio.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(left_panel, text="Filas pie ignorar:").pack(anchor="w", padx=5, pady=(2,0))
        self.ent_fila_pie = ctk.CTkEntry(left_panel)
        self.ent_fila_pie.pack(fill="x", padx=5, pady=2)

        self.btn_usar_fila = ctk.CTkButton(left_panel, text="📌 Usar fila como Inicio", command=self.usar_fila_seleccionada)
        self.btn_usar_fila.pack(fill="x", padx=5, pady=10)

        # Right Panels (Trees)
        right_panel = ctk.CTkFrame(main_frame)
        right_panel.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        right_panel.rowconfigure(0, weight=7)
        right_panel.rowconfigure(1, weight=3)
        right_panel.columnconfigure(0, weight=1)

        # Tree 1: Raw
        tree1_frame = ctk.CTkFrame(right_panel)
        tree1_frame.grid(row=0, column=0, sticky="nsew", pady=2)
        ctk.CTkLabel(tree1_frame, text="Tabla Cruda del Archivo (Clic derecho para asignar):").pack(anchor="w", padx=5)

        self.tree = ttk.Treeview(tree1_frame, columns=[], show="headings")
        self.tree.pack(fill="both", expand=True, side="left")
        scroll_y = ttk.Scrollbar(tree1_frame, orient="vertical", command=self.tree.yview)
        scroll_y.pack(side="right", fill="y")
        scroll_x = ttk.Scrollbar(self.tree, orient="horizontal", command=self.tree.xview)
        scroll_x.pack(side="bottom", fill="x")
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        # Context Menu for Tree 1
        self.menu_contextual = Menu(self, tearoff=0)
        self.menu_contextual.add_command(label="🎯 Asignar a CÓDIGO", command=lambda: self.asignar_col_context("CÓDIGO"))
        self.menu_contextual.add_command(label="📝 Asignar a DESCRIPCIÓN", command=lambda: self.asignar_col_context("DESCRIPCIÓN"))
        self.menu_contextual.add_command(label="🏷️ Asignar a MARCA", command=lambda: self.asignar_col_context("MARCA"))
        self.menu_contextual.add_command(label="💲 Asignar a PRECIO", command=lambda: self.asignar_col_context("PRECIO"))
        self.menu_contextual.add_command(label="➕ Agregar a EQUIVALENCIAS/DESC EXTRA", command=lambda: self.asignar_col_context("EQUIV"))
        self.menu_contextual.add_command(label="📌 Marcar fila como INICIO DE DATOS", command=self.usar_fila_seleccionada)

        self.tree.bind("<Button-3>", self.mostrar_menu)
        self.tree.bind("<Button-1>", self.on_tree_click) # For header click context

        # Tree 2: Live Preview
        tree2_frame = ctk.CTkFrame(right_panel)
        tree2_frame.grid(row=1, column=0, sticky="nsew", pady=2)
        ctk.CTkLabel(tree2_frame, text="Vista Previa de Productos Aprendidos:").pack(anchor="w", padx=5)

        self.tree_live = ttk.Treeview(tree2_frame, columns=("Codigo", "Descripcion", "Marca", "Costo", "Estado"), show="headings")
        self.tree_live.heading("Codigo", text="Código")
        self.tree_live.heading("Descripcion", text="Descripción Final Armada")
        self.tree_live.heading("Marca", text="Marca")
        self.tree_live.heading("Costo", text="$ Costo")
        self.tree_live.heading("Estado", text="Estado Validación")
        self.tree_live.pack(fill="both", expand=True, side="left")
        scroll_y2 = ttk.Scrollbar(tree2_frame, orient="vertical", command=self.tree_live.yview)
        scroll_y2.pack(side="right", fill="y")
        self.tree_live.configure(yscrollcommand=scroll_y2.set)

        for cmb in [self.cmb_col_cod, self.cmb_col_desc, self.cmb_col_precio, self.cmb_col_marca]:
            cmb.configure(command=self.on_combo_change)
        self.ent_cols_equiv.bind("<KeyRelease>", self.on_combo_change)
        self.ent_fila_inicio.bind("<KeyRelease>", self.on_combo_change)

        # Bottom Bar Layout Fix
        bottom_frame = ctk.CTkFrame(self, height=50)
        bottom_frame.pack(side="bottom", fill="x", padx=10, pady=10)

        self.lbl_prueba = ctk.CTkLabel(bottom_frame, text="")
        self.lbl_prueba.pack(side="left", padx=10)

        btn_probar = ctk.CTkButton(bottom_frame, text="🔍 Probar Regla en esta Vista", command=self.actualizar_live_preview)
        btn_probar.pack(side="right", padx=5)

        btn_guardar = ctk.CTkButton(bottom_frame, text="💾 Guardar Entrenamiento y Extraer Todo", fg_color="green", hover_color="darkgreen", command=self.guardar_y_extraer)
        btn_guardar.pack(side="right", padx=5)

    def mostrar_menu(self, event):
        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not col: return
        self.col_contextual = int(col.replace('#', '')) - 1 # #1 is Fila, #2 is Col 0
        if self.col_contextual < 0: return # Click on 'Fila' column

        if item:
            self.tree.selection_set(item)
        self.menu_contextual.post(event.x_root, event.y_root)

    def on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            col = self.tree.identify_column(event.x)
            if col:
                self.col_contextual = int(col.replace('#', '')) - 1
                if self.col_contextual >= 0:
                    self.menu_contextual.post(event.x_root, event.y_root)

    def asignar_col_context(self, tipo):
        val = str(self.col_contextual)
        if tipo == "CÓDIGO": self.cmb_col_cod.set(val)
        elif tipo == "DESCRIPCIÓN": self.cmb_col_desc.set(val)
        elif tipo == "MARCA": self.cmb_col_marca.set(val)
        elif tipo == "PRECIO": self.cmb_col_precio.set(val)
        elif tipo == "EQUIV":
            curr = self.ent_cols_equiv.get().strip()
            if curr: self.ent_cols_equiv.delete(0, tk.END); self.ent_cols_equiv.insert(0, f"{curr},{val}")
            else: self.ent_cols_equiv.insert(0, val)
        self.on_combo_change()

    def autodetectar(self):
        filas = self.preview_data.get(self.origen_actual, [])
        if not filas: return
        mapeo = self.motor.autodetectar_mapeo_columnas(filas)

        if mapeo["col_codigo"] is not None: self.cmb_col_cod.set(str(mapeo["col_codigo"]))
        if mapeo["col_descripcion"] is not None: self.cmb_col_desc.set(str(mapeo["col_descripcion"]))
        if mapeo["col_marca"] is not None: self.cmb_col_marca.set(str(mapeo["col_marca"]))
        if mapeo["col_precio"] is not None: self.cmb_col_precio.set(str(mapeo["col_precio"]))

        self.ent_cols_equiv.delete(0, tk.END)
        self.ent_cols_equiv.insert(0, ",".join(map(str, mapeo["cols_equivalencias"])))

        self.ent_fila_inicio.delete(0, tk.END)
        self.ent_fila_inicio.insert(0, str(mapeo["fila_inicio"]))

        self.on_combo_change()

    def on_modo_change(self, modo):
        perfil_gen = self.gestor_perfiles.obtener_perfil(self.proveedor, "PDF", "GENERAL")
        perfil_gen["modo_lectura_pdf"] = modo
        self.gestor_perfiles.guardar_perfil(self.proveedor, "PDF", "GENERAL", perfil_gen)
        # Reload preview data
        self.preview_data = self.motor.obtener_previsualizacion_cruda(self.ruta_archivo, self.gestor_perfiles, self.proveedor)
        self.cargar_tabla()

    def on_combo_change(self, *args):
        self.actualizar_cabeceras()
        self.actualizar_live_preview()

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

            perfil_gen = self.gestor_perfiles.obtener_perfil(self.proveedor, "PDF", "GENERAL")
            self.cmb_modo.set(perfil_gen.get("modo_lectura_pdf", "Automático Inteligente (Desglosado por renglón)"))

    def parsear_combo(self, cmb):
        v = cmb.get()
        if v == "Ninguna": return None
        try: return int(v)
        except: return None

    def setear_combo(self, cmb, val):
        if val is None: cmb.set("Ninguna")
        else: cmb.set(str(val))

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

        self.setear_combo(self.cmb_col_cod, perfil.get("col_codigo"))
        self.setear_combo(self.cmb_col_desc, perfil.get("col_descripcion"))
        self.setear_combo(self.cmb_col_precio, perfil.get("col_precio"))
        self.setear_combo(self.cmb_col_marca, perfil.get("col_marca"))

        self.ent_cols_equiv.delete(0, tk.END)
        self.ent_cols_equiv.insert(0, ",".join(map(str, perfil.get("cols_equivalencias", []))))

        self.ent_fila_inicio.delete(0, tk.END)
        self.ent_fila_inicio.insert(0, str(perfil.get("fila_inicio", 1)))

        self.ent_fila_pie.delete(0, tk.END)
        self.ent_fila_pie.insert(0, str(perfil.get("filas_pie_ignorar", 0)))

        self.cargar_tabla()

        # If new provider, try auto-detect
        if self.parsear_combo(self.cmb_col_cod) is None and self.parsear_combo(self.cmb_col_precio) is None:
            self.autodetectar()

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

    def cargar_tabla(self):
        self.tree.delete(*self.tree.get_children())
        filas = self.preview_data.get(self.origen_actual, [])
        if not filas: return

        max_cols = max(len(f) for f in filas)
        cols = ["Fila"] + [f"{i}" for i in range(max_cols)]
        self.tree.configure(columns=cols)

        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)

        for i, fila in enumerate(filas):
            # Pad with empty if needed
            padded = fila + [""] * (max_cols - len(fila))
            self.tree.insert("", "end", values=[str(i)] + padded)

        self.actualizar_cabeceras()
        self.actualizar_live_preview()

    def actualizar_cabeceras(self):
        try:
            cod = self.parsear_combo(self.cmb_col_cod)
            desc = self.parsear_combo(self.cmb_col_desc)
            prec = self.parsear_combo(self.cmb_col_precio)
            marc = self.parsear_combo(self.cmb_col_marca)

            ce_txt = self.ent_cols_equiv.get()
            ce = [int(x.strip()) for x in ce_txt.split(',') if x.strip().isdigit()]

            for col in self.tree["columns"]:
                if col == "Fila":
                    self.tree.heading(col, text="Fila")
                    continue
                try:
                    idx = int(col)
                    txt = f"Col {idx}"
                    tags = []
                    if idx == cod: tags.append("CÓDIGO")
                    if idx == desc: tags.append("DESC")
                    if idx == prec: tags.append("PRECIO")
                    if idx == marc: tags.append("MARCA")
                    if idx in ce: tags.append("EXTRA")

                    if tags:
                        txt += f" [{'+'.join(tags)}]"
                    self.tree.heading(col, text=txt)
                except: pass
        except: pass

    def usar_fila_seleccionada(self):
        sel = self.tree.selection()
        if not sel: return
        item = self.tree.item(sel[0])
        fila_idx = item["values"][0]
        self.ent_fila_inicio.delete(0, tk.END)
        self.ent_fila_inicio.insert(0, str(fila_idx))
        self.on_combo_change()

    def _obtener_perfil_ui(self):
        try: fi = int(self.ent_fila_inicio.get())
        except: fi = 1
        try: fp = int(self.ent_fila_pie.get())
        except: fp = 0

        ce_txt = self.ent_cols_equiv.get()
        ce = [int(x.strip()) for x in ce_txt.split(',') if x.strip().isdigit()]

        return {
            "activa": self.var_activa.get(),
            "col_codigo": self.parsear_combo(self.cmb_col_cod),
            "col_descripcion": self.parsear_combo(self.cmb_col_desc),
            "col_precio": self.parsear_combo(self.cmb_col_precio),
            "col_marca": self.parsear_combo(self.cmb_col_marca),
            "cols_equivalencias": ce,
            "fila_inicio": fi,
            "filas_pie_ignorar": fp,
            "paginas_ignoradas": [],
            "modo_multiline_baterias": False,
            "marca_fija": "",
            "modo_lectura_pdf": self.cmb_modo.get() if self.tipo_archivo == "PDF" else "auto_desglosado",
            "nombres_cabecera_aprendidos": {}
        }

    def actualizar_live_preview(self):
        perfil = self._obtener_perfil_ui()
        filas = self.preview_data.get(self.origen_actual, [])
        prods = self.motor._procesar_filas(filas, perfil, self.origen_actual)

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
        perfil = self._obtener_perfil_ui()

        # Save header names if we have a header row
        try:
            fi = perfil["fila_inicio"]
            filas = self.preview_data.get(self.origen_actual, [])
            if fi > 0 and len(filas) >= fi:
                header_row = filas[fi-1]
                aprendidos = {}
                if perfil["col_codigo"] is not None and perfil["col_codigo"] < len(header_row):
                    aprendidos["codigo"] = str(header_row[perfil["col_codigo"]])
                if perfil["col_descripcion"] is not None and perfil["col_descripcion"] < len(header_row):
                    aprendidos["descripcion"] = str(header_row[perfil["col_descripcion"]])
                if perfil["col_precio"] is not None and perfil["col_precio"] < len(header_row):
                    aprendidos["precio"] = str(header_row[perfil["col_precio"]])
                perfil["nombres_cabecera_aprendidos"] = aprendidos
        except: pass

        ident = "GENERAL" if self.tipo_archivo == "PDF" else self.origen_actual
        self.gestor_perfiles.guardar_perfil(self.proveedor, self.tipo_archivo, ident, perfil)

        if self.tipo_archivo == "EXCEL":
            hojas = self.gestor_perfiles.obtener_metadatos_excel(self.proveedor)
            if self.var_activa.get():
                if self.origen_actual not in hojas: hojas.append(self.origen_actual)
            else:
                if self.origen_actual in hojas: hojas.remove(self.origen_actual)
            self.gestor_perfiles.actualizar_metadatos_excel(self.proveedor, hojas)

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
        # Header (Fila 0)
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(header, text="BarterPlus Unificador", font=("Arial", 20, "bold")).pack(side="left", padx=10)

        self.lbl_db_estado = ctk.CTkLabel(header, text="Base: barterplus.db (Solo Lectura)", text_color="green")
        self.lbl_db_estado.pack(side="left", padx=20)

        self.lbl_perfiles = ctk.CTkLabel(header, text=f"🧠 Perfiles Entrenados: {len(self.gestor_perfiles.perfiles)}")
        self.lbl_perfiles.pack(side="right", padx=10)

        # Panel Carga (Fila 1)
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

        # ProgressBar
        self.progress = ctk.CTkProgressBar(self)
        self.progress.pack(fill="x", padx=10, pady=5)
        self.progress.set(0)

        # Hojas Excel Panel (Fila 2)
        self.panel_hojas = ctk.CTkFrame(self)

        # Auditoria (Fila 3 y 4)
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
