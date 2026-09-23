import unittest
import datetime as dt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db import Base, ImpuestoPeriodo
from db.models.costos import GastoNegocio
from services.costo_service import CostoService

class TestCostoService(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_calcular_total_fijos_mes(self):
        # Setup
        today = dt.date.today()
        # 1. Gasto directo
        g1 = GastoNegocio(fecha=today, monto=100.0, categoria="Test", descripcion="Directo")
        self.session.add(g1)

        # 2. Impuesto mensual
        start, end = CostoService._month_bounds(today)
        i1 = ImpuestoPeriodo(
            impuesto_id=1, periodo_label="Test",
            fecha_inicio=start, fecha_fin=end,
            monto=50.0, periodicidad="MENSUAL"
        )
        self.session.add(i1)
        self.session.commit()

        # Calculate
        total = CostoService.calcular_total_fijos_mes(self.session, today)
        self.assertEqual(total, 150.0)

    def test_prorrateo_bimestral(self):
        today = dt.date.today()
        start, end = CostoService._month_bounds(today)
        # Impuesto bimestral de 200 => 100 por mes
        i2 = ImpuestoPeriodo(
            impuesto_id=2, periodo_label="Bi",
            fecha_inicio=start, fecha_fin=end, # Mocking range overlap
            monto=200.0, periodicidad="BIMESTRAL"
        )
        self.session.add(i2)
        self.session.commit()

        total = CostoService.calcular_total_fijos_mes(self.session, today)
        self.assertEqual(total, 100.0)

if __name__ == '__main__':
    unittest.main()
