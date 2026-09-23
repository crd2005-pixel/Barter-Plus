import datetime as dt
from sqlalchemy import and_
from sqlalchemy.orm import Session
from db.models.costos import GastoNegocio, Impuesto, ImpuestoPeriodo, Empleado, SueldoLiquidacion
from db.models.costos_extra import CreditoNegocio, CreditoCuota, AdelantoSueldo

class CostoService:
    @staticmethod
    def _month_bounds(d: dt.date | None = None):
        d = d or dt.date.today()
        first = dt.date(d.year, d.month, 1)
        nxt = dt.date(d.year + (1 if d.month == 12 else 0), 1 if d.month == 12 else d.month + 1, 1)
        return first, nxt

    @staticmethod
    def _share_by_periodicity(periodicidad: str) -> int:
        p = (periodicidad or "").upper()
        return 1 if p=='MENSUAL' else 2 if p=='BIMESTRAL' else 3 if p=='TRIMESTRAL' else 12 if p=='ANUAL' else 1

    @classmethod
    def calcular_total_fijos_mes(cls, session: Session, ref: dt.date | None = None) -> float:
        """
        Calcula el total de gastos fijos prorrateados para el mes de referencia.
        """
        ini, fin = cls._month_bounds(ref)
        total = 0.0

        # 1. Impuestos prorrateados
        rows = session.query(ImpuestoPeriodo).filter(and_(ImpuestoPeriodo.fecha_inicio < fin,
                                                    ImpuestoPeriodo.fecha_fin >= ini)).all()
        for r in rows:
            div = cls._share_by_periodicity(getattr(r, "periodicidad", None))
            total += float(r.monto or 0.0) / max(div,1)

        # 2. Gastos de negocio directos
        gns = session.query(GastoNegocio).filter(and_(GastoNegocio.fecha >= ini, GastoNegocio.fecha < fin)).all()
        total += sum(float(g.monto or 0.0) for g in gns)

        # 3. Sueldos (Neto)
        per = f"{ini.year}-{ini.month:02d}"
        sues = session.query(SueldoLiquidacion).filter(SueldoLiquidacion.periodo_label == per).all()
        total += sum(float(su.neto or 0.0) for su in sues)

        # 4. Adelantos de sueldo
        ads = session.query(AdelantoSueldo).filter(and_(AdelantoSueldo.fecha >= ini, AdelantoSueldo.fecha < fin)).all()
        total += sum(float(a.monto or 0.0) for a in ads)

        # 5. Gastos generales (legacy/cross-module)
        try:
            from db.models.gastos import Gasto
            gastos_gral = session.query(Gasto).filter(
                Gasto.fecha >= ini,
                Gasto.fecha < fin,
                Gasto.tipo.in_(["fiscal", "negocio"])
            ).all()
            total += sum(float(g.monto or 0.0) for g in gastos_gral)
        except Exception:
            pass

        return float(round(total, 2))

    @classmethod
    def get_monthly_costs(cls, session: Session, year: int) -> list:
        """
        Retorna una lista de tuplas (mes, total) para todos los meses del año dado.
        mes: 1..12
        """
        results = []
        for month in range(1, 13):
            # Fecha de referencia: día 1 del mes
            ref_date = dt.date(year, month, 1)
            # Evitar calcular meses futuros si se desea, o dejarlo (serán 0 o proyecciones)
            # Calculamos todo el año.
            total = cls.calcular_total_fijos_mes(session, ref=ref_date)
            results.append((month, total))
        return results
