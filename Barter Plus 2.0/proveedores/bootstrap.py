import pathlib, sqlalchemy as sa
from sqlalchemy.orm import declarative_base, sessionmaker

MOD_DIR = pathlib.Path(__file__).resolve().parent
DB_DIR = MOD_DIR / "data"; DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "proveedores.sqlite3"
engine = sa.create_engine(f"sqlite:///{DB_PATH.as_posix()}", future=True)

Base = declarative_base(name="ProvBase")
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

class Proveedor(Base):
    __tablename__ = "fb_proveedor"
    id = sa.Column(sa.Integer, primary_key=True)
    nombre = sa.Column(sa.String(255), nullable=False)
    telefono = sa.Column(sa.String(64))
    cuit = sa.Column(sa.String(32))
    email = sa.Column(sa.String(255))
    rubro = sa.Column(sa.String(64))

class ListaPrecioProveedor(Base):
    __tablename__ = "fb_lista_precio_proveedor"
    id = sa.Column(sa.Integer, primary_key=True)
    proveedor_id = sa.Column(sa.Integer, sa.ForeignKey("fb_proveedor.id"), nullable=False)
    nombre = sa.Column(sa.String(255), nullable=False)
    fecha_creacion = sa.Column(sa.Date)

class ItemListaProveedor(Base):
    __tablename__ = "fb_item_lista_proveedor"
    id = sa.Column(sa.Integer, primary_key=True)
    lista_id = sa.Column(sa.Integer, sa.ForeignKey("fb_lista_precio_proveedor.id"), nullable=False)
    producto_codigo = sa.Column(sa.String(255), nullable=False)
    precio = sa.Column(sa.Float, nullable=False)
    descripcion = sa.Column(sa.Text)
    marca = sa.Column(sa.String(255))
    rubro_detectado = sa.Column(sa.String(255))
    presentacion = sa.Column(sa.String(255)) # Nuevo campo
    info_extra = sa.Column(sa.String(255))   # Nuevo campo

class FacturaProveedor(Base):
    __tablename__ = "fb_factura_proveedor"
    id = sa.Column(sa.Integer, primary_key=True)
    proveedor_id = sa.Column(sa.Integer, sa.ForeignKey("fb_proveedor.id"), nullable=False)
    numero = sa.Column(sa.String(64))
    tipo = sa.Column(sa.String(32))
    fecha = sa.Column(sa.Date)
    plazo_dias = sa.Column(sa.Integer)
    fecha_vencimiento = sa.Column(sa.Date)
    monto_total = sa.Column(sa.Float)
    estado = sa.Column(sa.String(32))
    descripcion = sa.Column(sa.Text)

class FacturaItem(Base):
    __tablename__ = "fb_factura_item"
    id = sa.Column(sa.Integer, primary_key=True)
    factura_id = sa.Column(sa.Integer, sa.ForeignKey("fb_factura_proveedor.id"), nullable=False)
    producto_id = sa.Column(sa.Integer, nullable=True) # ID en la DB principal (Main DB)
    codigo = sa.Column(sa.String(255))
    descripcion = sa.Column(sa.String(255))
    cantidad = sa.Column(sa.Float, default=0.0)
    precio_unitario = sa.Column(sa.Float, default=0.0)
    subtotal = sa.Column(sa.Float, default=0.0)

class MovimientoProveedor(Base):
    __tablename__ = "fb_movimiento_proveedor"
    id = sa.Column(sa.Integer, primary_key=True)
    proveedor_id = sa.Column(sa.Integer, sa.ForeignKey("fb_proveedor.id"), nullable=False)
    fecha = sa.Column(sa.Date)
    fecha_vencimiento = sa.Column(sa.Date)
    descripcion = sa.Column(sa.Text)
    forma_pago = sa.Column(sa.String(255))
    debe = sa.Column(sa.Float, default=0.0)
    haber = sa.Column(sa.Float, default=0.0)

def bootstrap():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info('fb_proveedor')").fetchall()]
        if "telefono" not in cols:
            conn.exec_driver_sql("ALTER TABLE fb_proveedor ADD COLUMN telefono VARCHAR(64)")

        # Migración de items
        cols_items = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info('fb_item_lista_proveedor')").fetchall()]
        if "presentacion" not in cols_items:
            conn.exec_driver_sql("ALTER TABLE fb_item_lista_proveedor ADD COLUMN presentacion VARCHAR(255)")
        if "info_extra" not in cols_items:
            conn.exec_driver_sql("ALTER TABLE fb_item_lista_proveedor ADD COLUMN info_extra VARCHAR(255)")

    return {
        "engine": engine,
        "SessionLocal": SessionLocal,
        "Proveedor": Proveedor,
        "ListaPrecioProveedor": ListaPrecioProveedor,
        "ItemListaProveedor": ItemListaProveedor,
        "FacturaProveedor": FacturaProveedor,
        "FacturaItem": FacturaItem,
        "MovimientoProveedor": MovimientoProveedor,
    }
