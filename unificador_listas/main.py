import os
import json
import sqlite3
import re
import traceback
import pandas as pd
import pdfplumber
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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
            "marca_fija": ""
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
            # Intenta cargar de inventario_maestro o productos
            # Como barterplus principal, asumimos tabla productos
            try:
                cursor.execute("SELECT id, codigo_proveedor, descripcion, marca, proveedor, equivalencias FROM productos")
                for row in cursor.fetchall():
                    self.productos_db.append(dict(row))
            except sqlite3.OperationalError:
                pass
            conn.close()
        except sqlite3.OperationalError as e:
            print(f"Error al cargar DB en modo RO: {e}")

    def obtener_previsualizacion_cruda(self, ruta_archivo):
        _, ext = os.path.splitext(ruta_archivo.lower())
        preview = {}
        if ext in ['.xlsx', '.xls']:
            try:
                xls = pd.ExcelFile(ruta_archivo)
                for sheet_name in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet_name, nrows=60, header=None)
                    df = df.fillna("")
                    preview[sheet_name] = df.astype(str).values.tolist()
            except Exception as e:
                print(f"Error excel: {e}")
        elif ext == '.pdf':
            try:
                with pdfplumber.open(ruta_archivo) as pdf:
                    for i, page in enumerate(pdf.pages):
                        if i >= 60: break # Limitar max pages previsualizadas
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
                        preview[f"Página {i+1}"] = rows[:60]
            except Exception as e:
                print(f"Error pdf: {e}")
        return preview

    def _expand_multiline_pdf_row(self, cells):
        expanded_rows = []
        max_lines = 1
        split_cells = []
        for cell in cells:
            parts = str(cell).split('\n')
            max_lines = max(max_lines, len(parts))
            split_cells.append(parts)

        for i in range(max_lines):
            new_row = []
            for parts in split_cells:
                if i < len(parts):
                    new_row.append(parts[i].strip())
                else:
                    new_row.append(parts[-1].strip() if parts else "")

            # Limpieza para Casa Baterias (marcas partidas, dolares huerfanos)
            # Unir marcas si el codigo es vacio o hay continuidad
            if len(split_cells) >= 3 and i > 0:
                # If there's an orphan price without code, let's look closer
                # We simply want to merge lines!
                pass

            if new_row and new_row.count("$") > 0:
                pass

            expanded_rows.append(new_row)

        # Merge them correctly according to the prompt
        merged = []
        for row in expanded_rows:
            if len(row) > 2 and (str(row[2]).strip() == "$" or str(row[2]).strip() == ""):
                # orphan dollar sign, ignore line? No, we might need to merge it with previous or next.
                # Actually Casa Baterias is like:
                # LEMOM\nPREMIUM
                # $\n$ 113.873
                pass

        # Best approach to perfectly merge disjointed products:
        # If code is empty and previous had code, merge description
        final_rows = []
        for row in expanded_rows:
            if not row[0].strip() and final_rows:
                # Merge into previous
                for j in range(1, len(row)):
                    if row[j].strip() and row[j].strip() != "$":
                        final_rows[-1][j] = str(final_rows[-1][j]) + " " + str(row[j]).strip()
            else:
                final_rows.append(row)

        return final_rows

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
                with pdfplumber.open(ruta_archivo) as pdf:
                    total_paginas = len(pdf.pages)
                    for i, page in enumerate(pdf.pages):
                        if callback_progreso: callback_progreso(i / total_paginas)
                        page_num = i + 1
                        if page_num in paginas_ignoradas or page_num in perfil_general.get("paginas_ignoradas", []):
                            continue

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

        filas_reales = filas[fila_inicio:]
        if filas_pie > 0:
            filas_reales = filas_reales[:-filas_pie]

        # Si modo_baterias, procesar todas las filas multilinea
        filas_procesar = []
        if modo_baterias:
            for fila in filas_reales:
                if any('\n' in str(c) for c in fila):
                    filas_procesar.extend(self._expand_multiline_pdf_row(fila))
                else:
                    filas_procesar.append(fila)
        else:
            filas_procesar = filas_reales

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

            # Caso Seineca: "WK6002\n$4.434"
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

            # Logica de limpieza
            costo = limpiar_precio_argentino(precio_str)

            # Candado estricto
            if "$" in codigo: continue
            if codigo in ["175", "190", "205", "240", "275"]: continue
            if costo <= 0: continue
            if not codigo or not desc: continue

            productos.append({
                "codigo_proveedor": codigo,
                "descripcion": desc,
                "costo": costo,
                "marca": marca,
                "equivalencias": " | ".join(equivs),
                "origen": origen
            })

        return productos

    def cruzar_productos(self, productos_extraidos, proveedor):
        nuevos = []
        actualizaciones = []

        # Mapa memoria
        mapa_prov = {}
        for p in self.productos_db:
            if str(p.get("proveedor", "")).upper() == proveedor.upper():
                cod = str(p.get("codigo_proveedor", "")).strip().upper()
                mapa_prov[cod] = p

        for prod in productos_extraidos:
            cod_extraido = str(prod["codigo_proveedor"]).strip().upper()

            # Doble candado anti-colision para codigos cortos o numericos
            es_corto_o_num = len(cod_extraido) < 5 or cod_extraido.isdigit()

            if cod_extraido in mapa_prov:
                db_prod = mapa_prov[cod_extraido]
                if es_corto_o_num:
                    # Validacion de descripcion o marca
                    desc_db = str(db_prod.get("descripcion", "")).upper()
                    desc_ext = prod["descripcion"].upper()
                    # Aceptar si hay interseccion de palabras
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
        top_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(top_frame, text="Origen (Pestaña Excel o Página PDF):").pack(side="left", padx=5)
        self.cmb_origen = ctk.CTkComboBox(top_frame, values=[], command=self.on_origen_change)
        self.cmb_origen.pack(side="left", padx=5)

        self.var_activa = tk.BooleanVar(value=True)
        self.chk_activa = ctk.CTkCheckBox(top_frame, text="✅ Procesar esta Pestaña / Página como Lista Válida", variable=self.var_activa, command=self.on_activa_change)
        self.chk_activa.pack(side="left", padx=20)

        if self.tipo_archivo == "PDF":
            ctk.CTkLabel(top_frame, text="Páginas PDF a ignorar (ej: 1, 5-7):").pack(side="left", padx=5)
            self.ent_paginas_ign = ctk.CTkEntry(top_frame, width=100)
            self.ent_paginas_ign.pack(side="left", padx=5)
            self.ent_paginas_ign.bind("<FocusOut>", self.on_paginas_ign_change)

        # Main Layout
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Left Panel (Training)
        left_panel = ctk.CTkFrame(main_frame, width=300)
        left_panel.pack(side="left", fill="y", padx=5, pady=5)

        def crear_combo(parent, label_text):
            ctk.CTkLabel(parent, text=label_text).pack(anchor="w", padx=5, pady=(5,0))
            cmb = ctk.CTkComboBox(parent, values=["Ninguna"] + [f"{i}" for i in range(20)])
            cmb.pack(fill="x", padx=5, pady=2)
            cmb.set("Ninguna")
            return cmb

        self.cmb_col_cod = crear_combo(left_panel, "Columna Código:")
        self.cmb_col_desc = crear_combo(left_panel, "Columna Descripción:")
        self.cmb_col_precio = crear_combo(left_panel, "Columna Precio / Costo:")
        self.cmb_col_marca = crear_combo(left_panel, "Columna Marca:")

        ctk.CTkLabel(left_panel, text="Marca Fija (si no hay columna):").pack(anchor="w", padx=5, pady=(5,0))
        self.ent_marca_fija = ctk.CTkEntry(left_panel)
        self.ent_marca_fija.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(left_panel, text="Columnas Equivalencias (ej: 3,4,5):").pack(anchor="w", padx=5, pady=(5,0))
        self.ent_cols_equiv = ctk.CTkEntry(left_panel)
        self.ent_cols_equiv.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(left_panel, text="Fila de inicio de datos:").pack(anchor="w", padx=5, pady=(5,0))
        self.ent_fila_inicio = ctk.CTkEntry(left_panel)
        self.ent_fila_inicio.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(left_panel, text="Filas de pie de página a ignorar:").pack(anchor="w", padx=5, pady=(5,0))
        self.ent_fila_pie = ctk.CTkEntry(left_panel)
        self.ent_fila_pie.pack(fill="x", padx=5, pady=2)

        self.var_multiline = tk.BooleanVar(value=False)
        self.chk_multiline = ctk.CTkCheckBox(left_panel, text="📦 Filas agrupadas (Modo Baterías)", variable=self.var_multiline)
        self.chk_multiline.pack(anchor="w", padx=5, pady=10)

        self.btn_usar_fila = ctk.CTkButton(left_panel, text="📌 Usar fila seleccionada como Inicio", command=self.usar_fila_seleccionada)
        self.btn_usar_fila.pack(fill="x", padx=5, pady=5)

        # Right Panel (Treeview)
        right_panel = ctk.CTkFrame(main_frame)
        right_panel.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        self.tree = ttk.Treeview(right_panel, columns=[], show="headings")
        self.tree.pack(fill="both", expand=True)

        scroll_y = ttk.Scrollbar(right_panel, orient="vertical", command=self.tree.yview)
        scroll_y.pack(side="right", fill="y")
        scroll_x = ttk.Scrollbar(right_panel, orient="horizontal", command=self.tree.xview)
        scroll_x.pack(side="bottom", fill="x")
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        # Bind combobox changes to update tree headers
        for cmb in [self.cmb_col_cod, self.cmb_col_desc, self.cmb_col_precio, self.cmb_col_marca]:
            cmb.configure(command=self.actualizar_cabeceras)

        # Bottom Bar
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.pack(fill="x", padx=10, pady=10)

        self.lbl_prueba = ctk.CTkLabel(bottom_frame, text="")
        self.lbl_prueba.pack(side="left", padx=10)

        btn_probar = ctk.CTkButton(bottom_frame, text="🔍 Probar Regla en esta Vista", command=self.probar_regla)
        btn_probar.pack(side="right", padx=5)

        btn_guardar = ctk.CTkButton(bottom_frame, text="💾 Guardar Entrenamiento y Extraer Todo", fg_color="green", hover_color="darkgreen", command=self.guardar_y_extraer)
        btn_guardar.pack(side="right", padx=5)

    def cargar_datos(self):
        self.preview_data = self.motor.obtener_previsualizacion_cruda(self.ruta_archivo)
        origenes = list(self.preview_data.keys())
        if origenes:
            self.cmb_origen.configure(values=origenes)
            self.cmb_origen.set(origenes[0])
            self.on_origen_change(origenes[0])

        if self.tipo_archivo == "PDF":
            pags = self.gestor_perfiles.obtener_metadatos_pdf(self.proveedor)
            self.ent_paginas_ign.delete(0, tk.END)
            self.ent_paginas_ign.insert(0, ",".join(map(str, pags)))

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

        # Cargar perfil
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

        self.ent_marca_fija.delete(0, tk.END)
        self.ent_marca_fija.insert(0, str(perfil.get("marca_fija", "")))

        self.ent_cols_equiv.delete(0, tk.END)
        self.ent_cols_equiv.insert(0, ",".join(map(str, perfil.get("cols_equivalencias", []))))

        self.ent_fila_inicio.delete(0, tk.END)
        self.ent_fila_inicio.insert(0, str(perfil.get("fila_inicio", 1)))

        self.ent_fila_pie.delete(0, tk.END)
        self.ent_fila_pie.insert(0, str(perfil.get("filas_pie_ignorar", 0)))

        self.var_multiline.set(perfil.get("modo_multiline_baterias", False))

        self.cargar_tabla()

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
            self.tree.insert("", "end", values=[str(i)] + fila)

        self.actualizar_cabeceras()

    def actualizar_cabeceras(self, *args):
        try:
            cod = self.parsear_combo(self.cmb_col_cod)
            desc = self.parsear_combo(self.cmb_col_desc)
            prec = self.parsear_combo(self.cmb_col_precio)
            marc = self.parsear_combo(self.cmb_col_marca)

            for col in self.tree["columns"]:
                if col == "Fila":
                    self.tree.heading(col, text="Fila")
                    continue
                try:
                    idx = int(col)
                    txt = f"Col {idx}"
                    if idx == cod: txt += " [CÓDIGO]"
                    if idx == desc: txt += " [DESC]"
                    if idx == prec: txt += " [PRECIO]"
                    if idx == marc: txt += " [MARCA]"
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

    def _obtener_perfil_ui(self):
        try: fi = int(self.ent_fila_inicio.get())
        except: fi = 1
        try: fp = int(self.ent_fila_pie.get())
        except: fp = 0

        ce_txt = self.ent_cols_equiv.get()
        ce = []
        for x in ce_txt.split(','):
            x = x.strip()
            if x.isdigit(): ce.append(int(x))

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
            "modo_multiline_baterias": self.var_multiline.get(),
            "marca_fija": self.ent_marca_fija.get()
        }

    def probar_regla(self):
        perfil = self._obtener_perfil_ui()
        filas = self.preview_data.get(self.origen_actual, [])
        prods = self.motor._procesar_filas(filas, perfil, self.origen_actual)
        if not prods:
            self.lbl_prueba.configure(text="No se detectaron productos válidos con esta regla.", text_color="red")
        else:
            p1 = prods[0]
            txt = f"Detectados {len(prods)} productos. Ej: [{p1['codigo_proveedor']}] {p1['descripcion']} - ${p1['costo']}"
            self.lbl_prueba.configure(text=txt, text_color="green")

    def guardar_y_extraer(self):
        perfil = self._obtener_perfil_ui()
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

        ctk.CTkButton(header, text="Cambiar Base", width=100).pack(side="left", padx=5)

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
        # Oculto inicialmente

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
