import os
import logging
import pandas as pd
from thefuzz import process
from db import SessionLocal, Producto
from productos.utils import margen_por_rubro

def _get_logger():
    logger = logging.getLogger("ActualizacionPrecios")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        # Always output to the current working directory where the script is executed
        log_path = os.path.join(os.getcwd(), "unmatched_review_queue.log")
        file_handler = logging.FileHandler(log_path, mode='a')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        logger.addHandler(file_handler)
    return logger

def procesar_actualizacion_precios(ruta_equivalencias, carpeta_listas_nuevas, config_proveedores=None, ruta_maestro=None):
    """
    Loop principal para recorrer listas de proveedores y actualizar el maestro de inventario.
    Utiliza config_proveedores (dict) para definir parámetros por archivo.
    Fallback a fuzzy matching con descripciones (threshold 85%).
    """
    if config_proveedores is None:
        config_proveedores = {}

    try:
        df_equiv = pd.read_excel(ruta_equivalencias)
    except Exception as e:
        print(f"Error al cargar archivo base de equivalencias: {e}")
        return 0

    if 'Codigo_Proveedor' in df_equiv.columns:
        df_equiv['Codigo_Proveedor'] = df_equiv['Codigo_Proveedor'].astype(str)
    else:
        print("El archivo de equivalencias no tiene la columna 'Codigo_Proveedor'.")
        return 0

    if not os.path.exists(carpeta_listas_nuevas):
        print("La carpeta de listas nuevas no existe.")
        return 0

    archivos_procesados = 0

    with SessionLocal() as session:
        # Load all product descriptions for fuzzy matching
        productos_master = session.query(Producto.id, Producto.nombre, Producto.sku, Producto.codigo_barras).all()
        nombres_master = {p.nombre: p for p in productos_master if p.nombre}
        nombres_list = list(nombres_master.keys())

        for archivo in os.listdir(carpeta_listas_nuevas):
            if archivo.endswith('.xlsx') or archivo.endswith('.xls'):
                ruta_lista = os.path.join(carpeta_listas_nuevas, archivo)
                print(f"--> Iniciando procesamiento de: {archivo}")

                # Fetch config or use defaults
                conf = config_proveedores.get(archivo, {})
                sheet_name = conf.get("sheet_name", 0) # default first sheet
                col_code = conf.get("col_code", "Codigo_Proveedor")
                col_desc = conf.get("col_desc", "Descripcion")
                col_cost = conf.get("col_cost", "Nuevo_Costo")

                try:
                    df_prov = pd.read_excel(ruta_lista, sheet_name=sheet_name)

                    if col_cost not in df_prov.columns:
                        print(f"El archivo {archivo} no tiene la columna de costo '{col_cost}'.")
                        continue

                    for index, fila in df_prov.iterrows():
                        codigo_prov = str(fila.get(col_code, "")).strip() if col_code in df_prov.columns else ""
                        desc_prov = str(fila.get(col_desc, "")).strip() if col_desc in df_prov.columns else ""

                        logger = _get_logger()
                        try:
                            nuevo_costo = float(fila[col_cost])
                        except (ValueError, TypeError):
                            logger.info(f"Fila {index} en {archivo}: Costo inválido '{fila.get(col_cost)}'. Skipped.")
                            continue

                        sku_interno = None
                        matched = False

                        # 1. Try exact match using equivalents table
                        if codigo_prov and codigo_prov != "nan":
                            match_equiv = df_equiv[df_equiv['Codigo_Proveedor'] == codigo_prov]
                            if not match_equiv.empty:
                                sku_interno = str(match_equiv.iloc[0]['SKU_Interno'])
                                matched = True

                        # 2. Try fuzzy matching if exact fails and we have a description
                        if not matched and desc_prov and desc_prov != "nan" and nombres_list:
                            best_match = process.extractOne(desc_prov, nombres_list)
                            if best_match:
                                match_name, score = best_match[0], best_match[1]
                                if score >= 85:
                                    # High confidence fuzzy match
                                    prod = nombres_master[match_name]
                                    sku_interno = prod.sku or prod.codigo_barras
                                    matched = True
                                else:
                                    logger.info(f"Fila {index} en {archivo}: Baja confianza ({score}%) para '{desc_prov}'. Skipped.")
                                    continue
                            else:
                                logger.info(f"Fila {index} en {archivo}: Sin match para '{desc_prov}'. Skipped.")
                                continue

                        if not matched:
                            logger.info(f"Fila {index} en {archivo}: Sin código ni descripción válida. Skipped.")
                            continue

                        # Buscar producto en la base de datos
                        producto = session.query(Producto).filter(Producto.sku == sku_interno).first()
                        if not producto:
                            producto = session.query(Producto).filter(Producto.codigo_barras == sku_interno).first()

                        if producto:
                            producto.costo = nuevo_costo

                            # Obtener el margen correspondiente a la categoría del producto
                            rubro = producto.rubro or ""
                            margen, _ = margen_por_rubro(rubro)

                            iva = float(producto.iva or 21.0)

                            tasa_iva = iva / 100.0
                            tasa_margen = margen / 100.0

                            if tasa_margen >= 1.0:
                                tasa_margen = 0.99

                            precio_venta = (nuevo_costo * (1.0 + tasa_iva)) / (1.0 - tasa_margen)
                            producto.precio_minorista = round(precio_venta, 2)

                    archivos_procesados += 1
                    print(f"✓ Archivo {archivo} procesado correctamente.")

                except Exception as e:
                    print(f"Error procesando el archivo {archivo}: {e}")

        if archivos_procesados > 0:
            try:
                session.commit()
                print(f"\n[ÉXITO] Proceso terminado. Se actualizaron datos basados en {archivos_procesados} lista(s).")
            except Exception as e:
                session.rollback()
                print(f"\n[ERROR] No se pudo guardar en la base de datos: {e}")
        else:
            print("\n[INFO] No se realizaron modificaciones en el maestro.")

    return archivos_procesados
