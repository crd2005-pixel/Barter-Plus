import os
import json
import sqlite3

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
            # En un entorno real se podría registrar el log localmente aquí
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

def get_readonly_db_connection():
    db_path = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "BarterPlus", "barterplus.db")
    # Formatear la ruta adecuadamente para la URI de sqlite3
    db_uri = f"file:{os.path.abspath(db_path).replace(chr(92), '/')}?mode=ro"
    try:
        conn = sqlite3.connect(db_uri, uri=True)
        return conn
    except sqlite3.OperationalError as e:
        # En caso de que no exista la base o no haya permisos
        print(f"Error conectando a DB principal en modo RO: {e}")
        return None

if __name__ == "__main__":
    gestor = GestorPerfilesEntrenamiento()
    print("Gestor inicializado. Perfiles cargados:", len(gestor.perfiles))
