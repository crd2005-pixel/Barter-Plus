# tests/verify_salidas_persistence.py
import sys
import os
import datetime as dt
sys.path.append(os.getcwd())

from db import SessionLocal
from services.salidas_service import SalidasService
from db.models.costos import GastoNegocio, ImpuestoPeriodo, Impuesto, Empleado
from db.models.costos_extra import AdelantoSueldo

def verify_persistence():
    session = SessionLocal()

    # Setup data
    fecha = dt.date.today()

    # 1. Create dummy entities if needed
    imp = session.query(Impuesto).first()
    if not imp:
        imp = Impuesto(nombre="TestImpuesto", periodicidad="MENSUAL")
        session.add(imp)
        session.commit()

    emp = session.query(Empleado).first()
    if not emp:
        emp = Empleado(nombre="TestEmpleado")
        session.add(emp)
        session.commit()

    print(f"Using Impuesto ID: {imp.id}, Empleado ID: {emp.id}")

    # 2. Test Negocio
    print("Testing 'negocio'...")
    SalidasService.registrar_salida(
        session=session,
        fecha=fecha,
        medio="Efectivo",
        tipo_destino="negocio",
        monto=123.45,
        concepto="Test Gasto Negocio",
        observacion="Auto Test",
        entity_id=None
    )

    # 3. Test Fiscal
    print("Testing 'fiscal'...")
    SalidasService.registrar_salida(
        session=session,
        fecha=fecha,
        medio="Transferencia",
        tipo_destino="fiscal",
        monto=50.0,
        concepto="Test Impuesto",
        observacion="Auto Test",
        entity_id=imp.id
    )

    # 4. Test Sueldo
    print("Testing 'sueldo'...")
    SalidasService.registrar_salida(
        session=session,
        fecha=fecha,
        medio="Efectivo",
        tipo_destino="sueldo",
        monto=1000.0,
        concepto="Test Adelanto",
        observacion="Auto Test",
        entity_id=emp.id
    )

    # 5. Verify
    print("\nVerifying...")

    # Check GastoNegocio
    gn = session.query(GastoNegocio).filter(GastoNegocio.monto == 123.45).first()
    if gn:
        print(f"[OK] GastoNegocio found: {gn.descripcion}, Pagado: {gn.pagado}")
    else:
        print("[FAIL] GastoNegocio NOT found")

    # Check ImpuestoPeriodo
    ip = session.query(ImpuestoPeriodo).filter(ImpuestoPeriodo.monto == 50.0).first()
    if ip:
        print(f"[OK] ImpuestoPeriodo found: {ip.periodo_label}, Pagado: {ip.pagado}")
    else:
        print("[FAIL] ImpuestoPeriodo NOT found")

    # Check AdelantoSueldo
    adv = session.query(AdelantoSueldo).filter(AdelantoSueldo.monto == 1000.0).first()
    if adv:
        print(f"[OK] AdelantoSueldo found for emp {adv.empleado_id}, Pagado: {adv.pagado}")
    else:
        print("[FAIL] AdelantoSueldo NOT found")

    session.close()

if __name__ == "__main__":
    verify_persistence()
