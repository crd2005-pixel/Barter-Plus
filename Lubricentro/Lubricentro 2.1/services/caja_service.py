from typing import Dict, Any, Tuple
import datetime as dt
from sqlalchemy import func
from sqlalchemy.orm import Session
from db.models.caja import CierreCaja, CierreCajaAjuste
from db.models.ventas import Venta
from db.models.tarjetas import VentaPago
from db.models.clientes import CuentaCorrienteCliente
from db.models.gastos import Gasto

class CajaService:
    @staticmethod
    def medio_norm(s: str) -> str:
        s = (s or "").strip().lower()
        if "efect" in s:
            return "efectivo"
        if "transf" in s or "transfer" in s:
            return "transferencia"
        if "deb" in s:
            return "debito"
        if "tarj" in s or "cred" in s:
            return "credito"
        if "corrien" in s or "ctacte" in s or "cta cte" in s:
            return "ctacte"
        return ""

    @classmethod
    def estimados_sistema(cls, session: Session, start: dt.datetime, end: dt.datetime) -> Dict[str, float]:
        """
        Estimados del sistema para el rango:
        Ventas por medio + Cobros CtaCte (por medio, si el concepto lo indica) − Gastos por medio.
        """
        tot = dict(total=0.0, efectivo=0.0, transferencia=0.0, debito=0.0, credito=0.0, ctacte=0.0)

        # 1. Ventas
        # Si existe VentaPago, usamos eso para granularidad
        # Si no, fallback a Venta.forma_pago (legacy)

        # Check if VentaPago table exists and has data?
        # Assuming VentaPago is always the way forward if model exists.

        # NOTE: logic from original file handled VentaPago=None.
        # Here we assume it exists since we saw it in db/models/tarjetas.py

        q = (
            session.query(VentaPago.medio, func.sum(VentaPago.monto))
            .join(Venta, Venta.id == VentaPago.venta_id)
            .filter(Venta.fecha >= start, Venta.fecha <= end)
        )
        if hasattr(Venta, "estado"):
            q = q.filter(Venta.estado != "ANULADA")

        rows = q.group_by(VentaPago.medio).all()
        for medio, monto in rows:
            key = cls.medio_norm(medio)
            if key in tot:
                tot[key] += float(monto or 0.0)

        # 2. Cobros Cta Cte clientes (monto negativo). Medio en concepto "Cobro Cta Cte (medio)"
        cc_rows = (
            session.query(CuentaCorrienteCliente)
            .filter(CuentaCorrienteCliente.fecha >= start, CuentaCorrienteCliente.fecha <= end,
                    CuentaCorrienteCliente.monto < 0)
            .all()
        )
        for mov in cc_rows:
            desc = getattr(mov, "concepto", "") or ""
            medio = ""
            if "(" in desc and ")" in desc:
                try:
                    medio = desc.split("(")[1].split(")")[0]
                except Exception:
                    medio = ""
            key = cls.medio_norm(medio)
            if key in tot:
                tot[key] += float(abs(mov.monto))

        # 3. Gastos restan
        if Gasto:
            g_rows = (
                session.query(Gasto.medio, func.sum(Gasto.monto))
                .filter(Gasto.fecha >= start, Gasto.fecha <= end)
                .group_by(Gasto.medio)
                .all()
            )
            for medio, monto in g_rows:
                key = cls.medio_norm(medio)
                if key in tot:
                    tot[key] -= float(monto or 0.0)

        tot["total"] = sum(v for k, v in tot.items() if k != "total")
        return tot

    @classmethod
    def crear_precierre(cls, session: Session, start: dt.datetime, end: dt.datetime, data: Dict[str, Any]) -> CierreCaja:
        est = cls.estimados_sistema(session, start, end)

        dif = dict(
            efectivo = data["efectivo"] - est["efectivo"],
            transferencia = data["transferencia"] - est["transferencia"],
            debito = data["debito"] - est["debito"],
            credito = data["credito"] - est["credito"],
            ctacte = data["ctacte"] - est["ctacte"],
        )

        c = CierreCaja(
            fecha_desde=start, fecha_hasta=end,
            total=float(est["total"]),

            total_efectivo=float(est["efectivo"]),
            total_transferencia=float(est["transferencia"]),
            total_debito=float(est["debito"]),
            total_credito=float(est["credito"]),
            total_ctacte=float(est["ctacte"]),

            contado_efectivo=float(data["efectivo"]),
            contado_transferencia=float(data["transferencia"]),
            contado_debito=float(data["debito"]),
            contado_credito=float(data["credito"]),
            contado_ctacte=float(data["ctacte"]),

            dif_efectivo=float(dif["efectivo"]),
            dif_transferencia=float(dif["transferencia"]),
            dif_debito=float(dif["debito"]),
            dif_credito=float(dif["credito"]),
            dif_ctacte=float(dif["ctacte"]),

            estado="PREC",
            motivo_diferencia=(data["obs"] or "")
        )
        session.add(c)
        session.commit()
        return c

    @classmethod
    def cerrar_caja(cls, session: Session, cierre_id: int, motivo: str) -> CierreCaja:
        c = session.get(CierreCaja, cierre_id)
        if not c:
            raise ValueError("Cierre no encontrado")

        dif_total = (
            float(getattr(c, "dif_efectivo", 0.0)) +
            float(getattr(c, "dif_transferencia", 0.0)) +
            float(getattr(c, "dif_debito", 0.0)) +
            float(getattr(c, "dif_credito", 0.0)) +
            float(getattr(c, "dif_ctacte", 0.0))
        )

        if abs(dif_total) > 0.0001:
             # Ajuste automático
            aj = CierreCajaAjuste(
                cierre_id=c.id,
                monto=float(dif_total),
                nota=motivo
            )
            session.add(aj)

        c.estado = "FINAL"
        c.motivo_diferencia = motivo
        session.commit()
        return c
