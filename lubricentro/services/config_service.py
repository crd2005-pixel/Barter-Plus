from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from db.models.configuracion import Configuracion
from db.models.tarjetas import TarjetaCoef

class ConfigService:
    _defaults_tarjetas = {
        "Visa": {1: 0.0, 3: 5.0, 6: 8.0, 12: 12.0},
        "MasterCard": {1: 0.0, 3: 4.0, 6: 7.0, 12: 11.0},
        "Cabal": {1: 0.0, 3: 3.0, 6: 5.0, 12: 9.0}
    }

    @classmethod
    def get_config(cls, session: Session) -> Configuracion:
        """Obtiene la configuración global del sistema."""
        cfg = session.query(Configuracion).first()
        if not cfg:
            cfg = Configuracion(nombre_negocio="Barter Plus")
            session.add(cfg)
            session.commit()
        return cfg

    @classmethod
    def get_tarjeta_coefs(cls, session: Session) -> Dict[str, Dict[int, float]]:
        """
        Retorna un dict {Marca: {Cuotas: Recargo}}.
        Si no hay datos en DB, retorna defaults.
        """
        try:
            rows = session.query(TarjetaCoef).all()
        except Exception:
            return cls._defaults_tarjetas

        if not rows:
            return cls._defaults_tarjetas

        res = {}
        for r in rows:
            res.setdefault(str(r.marca), {})[int(r.cuotas)] = float(r.recargo_pct)
        return res

    @classmethod
    def update_tarjeta_coef(cls, session: Session, marca: str, cuotas: int, recargo: float):
        """Actualiza o crea un coeficiente de tarjeta."""
        coef = session.query(TarjetaCoef).filter_by(marca=marca, cuotas=cuotas).first()
        if not coef:
            coef = TarjetaCoef(marca=marca, cuotas=cuotas)
            session.add(coef)
        coef.recargo_pct = recargo
        session.commit()
