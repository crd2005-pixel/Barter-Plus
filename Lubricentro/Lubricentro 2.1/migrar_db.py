# migrar_db.py
# ===========================
# Migraciones automáticas + seed inicial opcional
# ===========================

import sqlite3
from db import DB_PATH, SessionLocal, Deposito, Configuracion

# Tarjetas: el seed es opcional si el modelo existe y está exportado
try:
    from db import TarjetaPlan  # puede no existir en tu build
except Exception:
    TarjetaPlan = None

def ensure_table(db_path: str, table: str, cols_sql: str):
    con = sqlite3.connect(db_path)
    try:
        con.execute(f"CREATE TABLE IF NOT EXISTS {table} ({cols_sql})")
        con.commit()
    finally:
        con.close()

def ensure_column(db_path: str, table: str, column: str, ddl_fragment: str):
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(f"PRAGMA table_info({table});")
        cols = [r[1] for r in cur.fetchall()]
        if column not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_fragment};")
            con.commit()
    finally:
        con.close()

def exec_sql(db_path: str, sql: str, params: tuple | None = None):
    con = sqlite3.connect(db_path)
    try:
        con.execute(sql, params or ())
        con.commit()
    finally:
        con.close()

def run_migrations():
    # ---- Indexes Optimization
    exec_sql(DB_PATH, "CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas (fecha)")
    exec_sql(DB_PATH, "CREATE INDEX IF NOT EXISTS idx_cierre_caja_fecha ON cierre_caja (fecha_desde, fecha_hasta)")
    exec_sql(DB_PATH, "CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos (fecha)")

    # ---- Ventas / Productos
    ensure_column(DB_PATH, "ventas", "forma_pago", "TEXT DEFAULT 'Efectivo'")
    ensure_column(DB_PATH, "productos", "tiene_garantia", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(DB_PATH, "productos", "duracion_garantia_meses", "INTEGER NOT NULL DEFAULT 0")
    # New stock/bulk columns
    ensure_column(DB_PATH, "productos", "stock_minimo", "REAL NOT NULL DEFAULT 0.0")
    ensure_column(DB_PATH, "productos", "stock_maximo", "REAL NOT NULL DEFAULT 0.0")
    ensure_column(DB_PATH, "productos", "venta_granel", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(DB_PATH, "productos", "presentacion_cantidad", "REAL NOT NULL DEFAULT 1.0")
    ensure_column(DB_PATH, "productos", "presentacion_unidad", "TEXT DEFAULT 'Unidad'")
    ensure_column(DB_PATH, "productos", "subrubro", "TEXT")
    ensure_column(DB_PATH, "productos", "proveedor_id", "INTEGER") # Relación directa con tabla proveedores
    ensure_column(DB_PATH, "productos", "codigo_proveedor", "TEXT") # Código en lista proveedor
    ensure_column(DB_PATH, "productos", "precio_manual", "REAL NOT NULL DEFAULT 0") # Override manual de precio final

    ensure_column(DB_PATH, "ventas", "tarjeta_nombre", "TEXT NOT NULL DEFAULT ''")
    ensure_column(DB_PATH, "ventas", "tarjeta_cuotas", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(DB_PATH, "ventas", "tarjeta_interes_pct", "REAL NOT NULL DEFAULT 0")
    ensure_column(DB_PATH, "ventas", "tarjeta_total_con_interes", "REAL NOT NULL DEFAULT 0")
    ensure_column(DB_PATH, "ventas", "tarjeta_valor_cuota", "REAL NOT NULL DEFAULT 0")
    ensure_column(DB_PATH, "ventas", "efectivo_entrega", "REAL NOT NULL DEFAULT 0")
    ensure_column(DB_PATH, "ventas", "descuento", "REAL NOT NULL DEFAULT 0")
    ensure_column(DB_PATH, "ventas", "motivo_descuento", "TEXT DEFAULT ''")

    # ---- Filtros
    ensure_column(DB_PATH, "filtros", "vehiculo_aplicacion", "TEXT")
    ensure_column(DB_PATH, "filtros", "dimensiones", "TEXT")
    ensure_column(DB_PATH, "filtros", "precio", "REAL NOT NULL DEFAULT 0")
    ensure_column(DB_PATH, "filtros", "observaciones", "TEXT")

    # ---- Costos: tablas base
    ensure_table(DB_PATH, "gastos_negocio", """
        id INTEGER PRIMARY KEY,
        fecha DATE NOT NULL,
        categoria TEXT,
        descripcion TEXT,
        monto REAL NOT NULL DEFAULT 0,
        pagado INTEGER NOT NULL DEFAULT 0,
        credito_id INTEGER
    """)

    ensure_table(DB_PATH, "creditos_negocio", """
        id INTEGER PRIMARY KEY,
        descripcion TEXT NOT NULL,
        monto_total REAL NOT NULL DEFAULT 0,
        monto_cuota REAL NOT NULL DEFAULT 0,
        cant_cuotas INTEGER NOT NULL DEFAULT 1,
        fecha_inicio DATE NOT NULL,
        dia_vencimiento INTEGER NOT NULL DEFAULT 1
    """)

    ensure_table(DB_PATH, "creditos_cuotas", """
        id INTEGER PRIMARY KEY,
        credito_id INTEGER NOT NULL,
        fecha_venc DATE NOT NULL,
        monto REAL NOT NULL DEFAULT 0,
        pagado INTEGER NOT NULL DEFAULT 0
    """)

    ensure_table(DB_PATH, "sueldos_adelantos", """
        id INTEGER PRIMARY KEY,
        empleado_id INTEGER NOT NULL,
        fecha DATE NOT NULL,
        monto REAL NOT NULL DEFAULT 0,
        pagado INTEGER NOT NULL DEFAULT 0
    """)

    # ---- Costos: columnas que pueden faltar si ya existían
    ensure_column(DB_PATH, "gastos_negocio", "pagado", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(DB_PATH, "gastos_negocio", "credito_id", "INTEGER")

    # ---- Impuestos: columnas nuevas que usa el código
    ensure_column(DB_PATH, "impuestos_periodos", "pagado", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(DB_PATH, "impuestos_periodos", "fecha_pago", "DATE")
    ensure_column(DB_PATH, "impuestos_periodos", "periodicidad", "TEXT NOT NULL DEFAULT 'MENSUAL'")

    # Backfill de periodicidad NULL → 'MENSUAL' (por si la columna existía sin default)
    exec_sql(DB_PATH, "UPDATE impuestos_periodos SET periodicidad='MENSUAL' WHERE periodicidad IS NULL")

    # ---- Seed básico
    with SessionLocal() as s:
        if not s.query(Deposito).filter_by(nombre="Principal").first():
            s.add(Deposito(nombre="Principal")); s.commit()
        if not s.query(Configuracion).first():
            s.add(Configuracion(nombre_negocio="Barter Plus")); s.commit()

        # Seed tarjetas solo si el modelo existe y está mapeado
        if TarjetaPlan is not None:
            if s.query(TarjetaPlan).count() == 0:
                tarjetas = ['Genérica', 'Visa', 'Master', 'Naranja', 'Amex']
                cuotas_set = ["1", "3", "6", "12", "18", "24"]
                for t in tarjetas:
                    for c in cuotas_set:
                        s.add(TarjetaPlan(banco=t, nombre=t, tipo="Crédito", cuotas=c, interes=0.0))
                s.commit()

    print("Migraciones ejecutadas correctamente.")

if __name__ == "__main__":
    run_migrations()
