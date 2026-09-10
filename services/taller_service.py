from database.conexion import get_session
from database.models.taller import Vehiculo, GarantiaBateria, CambioAceite
from sqlalchemy import select
import datetime as dt
import uuid
import qrcode
from PIL import Image
from io import BytesIO
from typing import List, Optional

class TallerService:

    # --- VEHICULOS ---
    @staticmethod
    def crear_vehiculo(cliente_id: int, dominio: str, marca: str = "", modelo: str = "", anio: int = 0) -> Vehiculo:
        with get_session() as session:
            try:
                # Check if exists
                v_exist = session.scalars(select(Vehiculo).where(Vehiculo.dominio == dominio)).first()
                if v_exist:
                    raise ValueError(f"El vehículo con dominio {dominio} ya existe.")

                v = Vehiculo(
                    cliente_id=cliente_id,
                    dominio=dominio.upper(),
                    marca=marca,
                    modelo=modelo,
                    anio=anio if anio > 0 else None
                )
                session.add(v)
                session.commit()
                session.refresh(v)
                session.expunge(v)
                return v
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def obtener_vehiculos_por_cliente(cliente_id: int) -> List[Vehiculo]:
        from sqlalchemy.orm import joinedload
        with get_session() as session:
            v_list = session.scalars(
                select(Vehiculo)
                .options(joinedload(Vehiculo.cliente))
                .where(Vehiculo.cliente_id == cliente_id)
            ).all()
            for v in v_list:
                session.expunge(v)
            return list(v_list)

    @staticmethod
    def obtener_vehiculo_por_dominio(dominio: str) -> Optional[Vehiculo]:
        from sqlalchemy.orm import joinedload
        with get_session() as session:
            v = session.scalars(
                select(Vehiculo)
                .options(joinedload(Vehiculo.cliente))
                .where(Vehiculo.dominio == dominio.upper())
            ).first()
            if v:
                session.expunge(v)
            return v


    # --- GARANTÍAS DE BATERÍAS ---
    @staticmethod
    def registrar_garantia(vehiculo_id: int, producto_id: int, meses: int) -> GarantiaBateria:
        with get_session() as session:
            try:
                from dateutil.relativedelta import relativedelta
                hoy = dt.date.today()
                vencimiento = hoy + relativedelta(months=meses)
                codigo = str(uuid.uuid4())[:8].upper()

                g = GarantiaBateria(
                    vehiculo_id=vehiculo_id,
                    producto_id=producto_id,
                    fecha_instalacion=hoy,
                    meses_garantia=meses,
                    fecha_vencimiento=vencimiento,
                    codigo_garantia=f"GAR-{codigo}"
                )
                session.add(g)
                session.commit()
                session.refresh(g)
                session.expunge(g)
                return g
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def obtener_garantias(vehiculo_id: int) -> List[GarantiaBateria]:
        from sqlalchemy.orm import joinedload
        with get_session() as session:
            g_list = session.scalars(
                select(GarantiaBateria)
                .options(joinedload(GarantiaBateria.producto), joinedload(GarantiaBateria.vehiculo))
                .where(GarantiaBateria.vehiculo_id == vehiculo_id)
                .order_by(GarantiaBateria.fecha_instalacion.desc())
            ).all()
            for g in g_list:
                session.expunge(g)
            return list(g_list)


    # --- CAMBIOS DE ACEITE ---
    @staticmethod
    def registrar_cambio_aceite(vehiculo_id: int, km_actual: int, proximo_km: int,
                                aceite: str, f_aceite: bool, f_aire: bool,
                                f_comb: bool, f_hab: bool, obs: str = "") -> CambioAceite:
        with get_session() as session:
            try:
                c = CambioAceite(
                    vehiculo_id=vehiculo_id,
                    fecha=dt.date.today(),
                    km_actual=km_actual,
                    proximo_km=proximo_km,
                    aceite_utilizado=aceite,
                    filtro_aceite=f_aceite,
                    filtro_aire=f_aire,
                    filtro_combustible=f_comb,
                    filtro_habitaculo=f_hab,
                    observaciones=obs
                )
                session.add(c)
                session.commit()
                session.refresh(c)
                session.expunge(c)
                return c
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    def obtener_cambios_aceite(vehiculo_id: int) -> List[CambioAceite]:
        from sqlalchemy.orm import joinedload
        with get_session() as session:
            c_list = session.scalars(
                select(CambioAceite)
                .options(joinedload(CambioAceite.vehiculo))
                .where(CambioAceite.vehiculo_id == vehiculo_id)
                .order_by(CambioAceite.fecha.desc())
            ).all()
            for c in c_list:
                session.expunge(c)
            return list(c_list)


    # --- GENERACIÓN DE QR ---
    @staticmethod
    def generar_qr_garantia(garantia_id: int) -> bytes:
        """Genera el código QR para una Garantía y retorna los bytes de la imagen en formato PNG."""
        from sqlalchemy.orm import joinedload
        with get_session() as session:
            g = session.scalars(
                select(GarantiaBateria)
                .options(
                    joinedload(GarantiaBateria.producto),
                    joinedload(GarantiaBateria.vehiculo).joinedload(Vehiculo.cliente)
                )
                .where(GarantiaBateria.id == garantia_id)
            ).first()

            if not g:
                raise ValueError("Garantía no encontrada.")

            texto_qr = (
                f"--- GARANTÍA BATERÍA ---\n"
                f"Cliente: {g.vehiculo.cliente.nombre}\n"
                f"Vehículo: {g.vehiculo.dominio} ({g.vehiculo.marca} {g.vehiculo.modelo})\n"
                f"Batería: {g.producto.nombre}\n"
                f"Instalación: {g.fecha_instalacion.strftime('%d/%m/%Y')}\n"
                f"Vencimiento: {g.fecha_vencimiento.strftime('%d/%m/%Y')}\n"
                f"Código Único: {g.codigo_garantia}"
            )

            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(texto_qr)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            byte_io = BytesIO()
            img.save(byte_io, 'PNG')
            return byte_io.getvalue()

    @staticmethod
    def generar_qr_aceite(cambio_id: int) -> bytes:
        """Genera el código QR para un Cambio de Aceite y retorna los bytes de la imagen en formato PNG."""
        from sqlalchemy.orm import joinedload
        with get_session() as session:
            c = session.scalars(
                select(CambioAceite)
                .options(joinedload(CambioAceite.vehiculo).joinedload(Vehiculo.cliente))
                .where(CambioAceite.id == cambio_id)
            ).first()

            if not c:
                raise ValueError("Cambio de aceite no encontrado.")

            filtros = []
            if c.filtro_aceite: filtros.append("Aceite")
            if c.filtro_aire: filtros.append("Aire")
            if c.filtro_combustible: filtros.append("Combustible")
            if c.filtro_habitaculo: filtros.append("Habitáculo")
            filtros_str = ", ".join(filtros) if filtros else "Ninguno"

            texto_qr = (
                f"--- SERVICE LUBRICENTRO ---\n"
                f"Vehículo: {c.vehiculo.dominio} ({c.vehiculo.marca} {c.vehiculo.modelo})\n"
                f"Fecha: {c.fecha.strftime('%d/%m/%Y')}\n"
                f"Km Actual: {c.km_actual}\n"
                f"Próximo Km: {c.proximo_km}\n"
                f"Aceite: {c.aceite_utilizado}\n"
                f"Filtros Cambiados: {filtros_str}"
            )

            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(texto_qr)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            byte_io = BytesIO()
            img.save(byte_io, 'PNG')
            return byte_io.getvalue()
