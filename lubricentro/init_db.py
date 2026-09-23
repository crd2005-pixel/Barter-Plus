# init_db.py
# ===========================
# Script de inicialización de la base de datos
# ===========================

import datetime as dt
from db import (
    Base, engine, SessionLocal,
    Configuracion, Deposito, TarjetaCoef,
    Cliente, Producto, Venta, VentaItem
)

def init_database():
    """Crea tablas y carga datos básicos si no existen."""
    Base.metadata.create_all(engine)

    with SessionLocal() as s:
        cfg = s.query(Configuracion).first()
        if not cfg:
            cfg = Configuracion(clave_admin='1234', nombre_negocio='Barter Plus')
            s.add(cfg)
            print("➕ Configuración base creada.")

        dep = s.query(Deposito).first()
        if not dep:
            dep = Deposito(nombre='Principal')
            s.add(dep)
            print("➕ Depósito principal creado.")

        cf = s.query(Cliente).filter(Cliente.nombre == 'Consumidor Final').first()
        if not cf:
            cf = Cliente(nombre='Consumidor Final', condicion_iva='Consumidor Final')
            s.add(cf)
            print("➕ Cliente Consumidor Final creado.")

        p1 = s.query(Producto).filter(Producto.nombre == 'Aceite 10W40').first()
        if not p1:
            p1 = Producto(nombre='Aceite 10W40', codigo_barras='7790001000010', precio_minorista=10000.0, iva=21.0, activo=True)
            s.add(p1)
        p2 = s.query(Producto).filter(Producto.nombre == 'Batería 12V 65Ah').first()
        if not p2:
            p2 = Producto(nombre='Batería 12V 65Ah', codigo_barras='7790001000027', precio_minorista=95000.0, iva=21.0, activo=True)
            s.add(p2)
            print("➕ Productos de prueba creados.")

        if s.query(TarjetaCoef).count() == 0:
            for t in ('Visa', 'MasterCard'):
                for c in (3, 6, 12):
                    s.add(TarjetaCoef(marca=t, cuotas=c, recargo_pct=0.0))
            print("➕ Planes de tarjeta cargados.")

        s.commit()

        if s.query(Venta).count() == 0:
            v = Venta(
                numero=1,
                cliente_id=cf.id if cf else None,
                fecha=dt.datetime.utcnow(),
                rubro='General',
                forma_pago='Efectivo',
                total_neto=0.0,
                total_iva=0.0,
                total=0.0,
                estado='emitido',
            )
            s.add(v)
            s.flush()

            total = 0.0
            for prod, cant in ((p1, 1), (p2, 1)):
                if prod:
                    pu = float(prod.precio_minorista or 0)
                    subtotal = pu * cant
                    it = VentaItem(venta_id=v.id, producto_id=prod.id, cantidad=cant, precio_unitario=pu, subtotal=subtotal, iva=float(prod.iva or 21.0))
                    s.add(it)
                    total += subtotal
            v.total_neto = total
            v.total = total
            s.commit()
            print("🧪 Venta de prueba creada.")

    print("✅ Base de datos inicializada correctamente.")

if __name__ == "__main__":
    init_database()
