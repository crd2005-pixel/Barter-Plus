import datetime as dt
from typing import Optional
from sqlalchemy.orm import Session
from db.models.costos import GastoNegocio, Impuesto, ImpuestoPeriodo, Empleado
from db.models.costos_extra import AdelantoSueldo
from db.models.gastos import Gasto

class SalidasService:
    @staticmethod
    def registrar_salida(session: Session, fecha: dt.date, medio: str,
                         tipo_destino: str, monto: float,
                         concepto: str, observacion: str,
                         entity_id: Optional[int] = None):
        """
        Registra una salida y la redirige a la tabla de costos correspondiente.
        tipo_destino: 'fiscal' (Impuestos), 'negocio' (GastoNegocio), 'sueldo' (AdelantoSueldo), 'proveedor' (managed elsewhere or here), 'otro'
        entity_id: ID del impuesto o empleado si aplica.
        """
        # 1. Siempre registrar en Gasto (Caja Movimiento mirror)
        # Esto mantiene la consistencia de caja.
        g = Gasto(
            fecha=dt.datetime.combine(fecha, dt.time(hour=12)),
            medio=medio,
            monto=monto,
            concepto=concepto,
            observacion=observacion,
            tipo=tipo_destino
        )
        session.add(g)
        session.flush() # Para tener ID si fuera necesario

        # 2. Redirigir a Costos según tipo
        if tipo_destino == "fiscal":
            if entity_id:
                # Crear un periodo "ad hoc" o pago parcial
                per = ImpuestoPeriodo(
                    impuesto_id=entity_id,
                    periodo_label=f"Pago {fecha.strftime('%Y-%m-%d')}",
                    fecha_inicio=fecha,
                    fecha_fin=fecha,
                    monto=monto,
                    pagado=True,
                    periodicidad="EVENTUAL"
                )
                session.add(per)

        elif tipo_destino == "sueldo":
            # Adelanto de sueldo
            if entity_id:
                adv = AdelantoSueldo(
                    empleado_id=entity_id,
                    fecha=fecha,
                    monto=monto,
                    pagado=True # Ya salió la plata
                )
                session.add(adv)

        elif tipo_destino == "negocio":
            # Gasto directo del negocio
            gn = GastoNegocio(
                fecha=fecha,
                categoria="General", # Podría ser un input
                descripcion=f"{concepto} ({observacion})",
                monto=monto,
                pagado=True
            )
            session.add(gn)

        session.commit()
