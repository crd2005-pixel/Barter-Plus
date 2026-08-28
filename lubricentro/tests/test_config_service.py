import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db import Base
from db.models.configuracion import Configuracion
from db.models.tarjetas import TarjetaCoef
from services.config_service import ConfigService

class TestConfigService(unittest.TestCase):
    def setUp(self):
        # In-memory DB
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_get_config(self):
        # Should create defaults if empty
        cfg = ConfigService.get_config(self.session)
        self.assertIn(cfg.nombre_negocio, [None, "Barter Plus"])

        # Modify and retrieve
        cfg.nombre_negocio = "Test Shop"
        self.session.commit()

        cfg2 = ConfigService.get_config(self.session)
        self.assertEqual(cfg2.nombre_negocio, "Test Shop")

    def test_get_tarjeta_coefs_defaults(self):
        # Should return defaults when table is empty
        coefs = ConfigService.get_tarjeta_coefs(self.session)
        self.assertIn("Visa", coefs)
        self.assertIn(12, coefs["Visa"])

    def test_update_and_get_tarjeta_coefs(self):
        ConfigService.update_tarjeta_coef(self.session, "TestCard", 3, 10.0)

        # This should return mixed defaults and DB?
        # Current logic: if rows exist, it returns ONLY DB rows.
        # Let's verify behavior. Ideally we might want to merge, but simple logic says DB overrides all if present.

        # NOTE: The implementation says: "If not rows: return defaults". Else return DB rows.
        # So if I add one row, I lose defaults. This is expected behavior for "overriding default logic".

        coefs = ConfigService.get_tarjeta_coefs(self.session)
        self.assertIn("TestCard", coefs)
        self.assertEqual(coefs["TestCard"][3], 10.0)

        # Check if "Visa" is gone (since we have custom data now)
        # If this behavior is undesired, we should fix the service.
        # But for now let's assert the current logic.
        self.assertNotIn("Visa", coefs)

if __name__ == '__main__':
    unittest.main()
