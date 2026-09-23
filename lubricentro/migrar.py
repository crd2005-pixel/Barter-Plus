# migrar.py
# ======================
# Script de migraciones automáticas simples (SQLite)
# ======================

import sqlite3
from db import DB_PATH


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table});")
    cols = [c[1] for c in cursor.fetchall()]
    return column in cols


def ensure_column(cursor, table: str, column: str, ddl: str):
    if not column_exists(cursor, table, column):
        print(f"➕ Agregando columna {column} en {table}...")
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl};")


# --------------------------
# MIGRACIONES
# --------------------------

def migrate_productos(cursor):
    print("🔎 Revisando tabla productos...")
    ensure_column(cursor, "productos", "tiene_garantia", "BOOLEAN DEFAULT 0")
    ensure_column(cursor, "productos", "duracion_garantia_meses", "INTEGER DEFAULT 0")


def migrate_ventas(cursor):
    print("🔎 Revisando tabla ventas...")
    ensure_column(cursor, "ventas", "forma_pago", "TEXT DEFAULT 'Efectivo'")
    ensure_column(cursor, "ventas", "tarjeta_nombre", "TEXT DEFAULT ''")
    ensure_column(cursor, "ventas", "tarjeta_cuotas", "INTEGER DEFAULT 1")
    ensure_column(cursor, "ventas", "tarjeta_interes_pct", "REAL DEFAULT 0")
    ensure_column(cursor, "ventas", "tarjeta_total_con_interes", "REAL DEFAULT 0")
    ensure_column(cursor, "ventas", "tarjeta_valor_cuota", "REAL DEFAULT 0")
    ensure_column(cursor, "ventas", "efectivo_entrega", "REAL DEFAULT 0")


def migrate_clientes(cursor):
    print("🔎 Revisando tabla clientes...")
    ensure_column(cursor, "clientes", "cuit_dni", "TEXT")
    ensure_column(cursor, "clientes", "telefono", "TEXT")
    ensure_column(cursor, "clientes", "email", "TEXT")
    ensure_column(cursor, "clientes", "direccion", "TEXT")


def migrate_tarjeta_planes(cursor):
    print("🔎 Revisando tabla tarjeta_planes...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tarjeta_planes';")
    exists = cursor.fetchone()

    if not exists:
        print("⚠️ No existía tarjeta_planes → creando nueva...")
        cursor.execute("""
            CREATE TABLE tarjeta_planes (
                id INTEGER PRIMARY KEY,
                banco TEXT NOT NULL,
                nombre TEXT NOT NULL,
                tipo TEXT DEFAULT 'Crédito',
                cuotas TEXT NOT NULL,
                interes REAL DEFAULT 0.0,
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        return

    # Revisar columnas actuales
    cursor.execute("PRAGMA table_info(tarjeta_planes);")
    cols = [c[1] for c in cursor.fetchall()]

    # Si tiene la vieja "tarjeta" en vez de "nombre"
    if "tarjeta" in cols and "nombre" not in cols:
        print("🔄 Renombrando columna 'tarjeta' → 'nombre'...")
        cursor.execute("ALTER TABLE tarjeta_planes RENAME TO tarjeta_planes_old;")
        cursor.execute("""
            CREATE TABLE tarjeta_planes (
                id INTEGER PRIMARY KEY,
                banco TEXT,
                nombre TEXT,
                tipo TEXT DEFAULT 'Crédito',
                cuotas TEXT,
                interes REAL DEFAULT 0.0,
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            INSERT INTO tarjeta_planes (id, banco, nombre, tipo, cuotas, interes, fecha_creacion)
            SELECT id, banco, tarjeta, tipo, cuotas, interes, fecha_creacion
            FROM tarjeta_planes_old;
        """)
        cursor.execute("DROP TABLE tarjeta_planes_old;")
        return

    # Agregar faltantes
    expected = {
        "banco": "TEXT",
        "nombre": "TEXT",
        "tipo": "TEXT DEFAULT 'Crédito'",
        "cuotas": "TEXT",
        "interes": "REAL DEFAULT 0.0",
        "fecha_creacion": "DATETIME DEFAULT CURRENT_TIMESTAMP"
    }
    for col, ddl in expected.items():
        if col not in cols:
            print(f"➕ Agregando columna faltante {col} a tarjeta_planes...")
            cursor.execute(f"ALTER TABLE tarjeta_planes ADD COLUMN {col} {ddl};")


# --------------------------
# MAIN
# --------------------------
def run_migrations():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    migrate_productos(cur)
    migrate_ventas(cur)
    migrate_clientes(cur)
    migrate_tarjeta_planes(cur)

    con.commit()
    con.close()
    print("✅ Migraciones aplicadas correctamente.")


if __name__ == "__main__":
    run_migrations()
