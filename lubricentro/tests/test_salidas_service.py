import unittest
import datetime as dt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db import Base, Impuesto, Empleado
from db.models.costos import GastoNegocio, ImpuestoPeriodo
from db.models.costos_extra import AdelantoSueldo
from services.salidas_service import SalidasService

class TestSalidasService(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_registrar_gasto_negocio(self):
        SalidasService.registrar_salida(
            session=self.session,
            fecha=dt.date(2023, 1, 1),
            medio="Efectivo",
            tipo_destino="negocio",
            monto=100.0,
            concepto="Compra x",
            observacion="Test"
        )

        # Verify GastoNegocio
        gn = self.session.query(GastoNegocio).first()
        self.assertIsNotNone(gn)
        self.assertEqual(gn.monto, 100.0)
        self.assertEqual(gn.pagado, True)

    def test_registrar_adelanto_sueldo(self):
        emp = Empleado(nombre="Juan")
        self.session.add(emp)
        self.session.commit()

        SalidasService.registrar_salida(
            session=self.session,
            fecha=dt.date(2023, 1, 1),
            medio="Efectivo",
            tipo_destino="sueldo",
            monto=500.0,
            concepto="Adelanto",
            observacion="",
            entity_id=emp.id
        )

        adv = self.session.query(AdelantoSueldo).first()
        self.assertIsNotNone(adv)
        self.assertEqual(adv.monto, 500.0)
        self.assertEqual(adv.empleado_id, emp.id)

    def test_registrar_impuesto(self):
        imp = Impuesto(nombre="IVA", periodicidad="MENSUAL")
        self.session.add(imp)
        self.session.commit()

        SalidasService.registrar_salida(
            session=self.session,
            fecha=dt.date(2023, 1, 1),
            medio="Transferencia",
            tipo_destino="fiscal",
            monto=1000.0,
            concepto="Pago IVA",
            observacion="",
            entity_id=imp.id
        )

        per = self.session.query(ImpuestoPeriodo).first()
        self.assertIsNotNone(per)
        self.assertEqual(per.monto, 1000.0)
        self.assertEqual(per.impuesto_id, imp.id)
        self.assertTrue(per.pagado)

if __name__ == '__main__':
    unittest.main()
