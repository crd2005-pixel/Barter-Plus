from sqlalchemy.orm import Session
from db.models.pedidos import SolicitudProducto
import datetime as dt

class SolicitudService:
    @staticmethod
    def crear_solicitud(session: Session, texto: str, cliente_id: int = None):
        """Crea una nueva solicitud de producto."""
        if not texto or not texto.strip():
            raise ValueError("El texto del producto es obligatorio.")

        sol = SolicitudProducto(
            producto_texto=texto.strip(),
            cliente_id=cliente_id,
            fecha=dt.datetime.utcnow(),
            estado='pendiente'
        )
        session.add(sol)
        session.commit()
        return sol

    @staticmethod
    def listar_pendientes(session: Session):
        """Retorna todas las solicitudes en estado pendiente."""
        return session.query(SolicitudProducto)\
            .filter(SolicitudProducto.estado == 'pendiente')\
            .order_by(SolicitudProducto.fecha.desc())\
            .all()
