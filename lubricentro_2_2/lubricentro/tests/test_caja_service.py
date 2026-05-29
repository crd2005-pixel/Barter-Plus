import unittest
import datetime as dt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db import Base
from db.models.ventas import Venta
from db.models.caja import CierreCaja
from db.models.tarjetas import VentaPago
from services.caja_service import CajaService

class TestCajaService(unittest.TestCase):
    def setUp(self):
        # Use in-memory SQLite for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_estimados_sistema(self):
        # Create a sale
        v = Venta(fecha=dt.datetime.now(), total=100.0)
        self.session.add(v)
        self.session.flush()

        # Add payment
        vp = VentaPago(venta_id=v.id, medio="Efectivo", monto=100.0)
        self.session.add(vp)
        self.session.commit()

        start = dt.datetime.now() - dt.timedelta(days=1)
        end = dt.datetime.now() + dt.timedelta(days=1)

        estimados = CajaService.estimados_sistema(self.session, start, end)

        self.assertEqual(estimados["efectivo"], 100.0)
        self.assertEqual(estimados["total"], 100.0)

    def test_crear_precierre(self):
        start = dt.datetime.now() - dt.timedelta(hours=1)
        end = dt.datetime.now() + dt.timedelta(hours=1)
        data = {
            "efectivo": 100.0, # Physical count matches system (0 sales in this test case)
            "transferencia": 0.0,
            "debito": 0.0,
            "credito": 0.0,
            "ctacte": 0.0,
            "obs": "Test"
        }

        cierre = CajaService.crear_precierre(self.session, start, end, data)
        self.assertEqual(cierre.estado, "PREC")
        self.assertEqual(cierre.contado_efectivo, 100.0)
        self.assertEqual(cierre.dif_efectivo, 100.0) # Expected 0, counted 100 -> diff 100

    def test_cerrar_caja(self):
        # Setup a precierre first
        start = dt.datetime.now() - dt.timedelta(hours=1)
        end = dt.datetime.now() + dt.timedelta(hours=1)
        data = {
            "efectivo": 0.0,
            "transferencia": 0.0,
            "debito": 0.0,
            "credito": 0.0,
            "ctacte": 0.0,
            "obs": ""
        }
        cierre = CajaService.crear_precierre(self.session, start, end, data)

        final_cierre = CajaService.cerrar_caja(self.session, cierre.id, "All good")
        self.assertEqual(final_cierre.estado, "FINAL")
        self.assertEqual(final_cierre.motivo_diferencia, "All good")

if __name__ == '__main__':
    unittest.main()
