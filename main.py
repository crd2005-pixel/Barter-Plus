import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow

def main():
    from database.conexion import Base, engine, get_session
    from sqlalchemy import text
    import hashlib
    # Asegurar que la base de datos existe (solo crea si no existe)
    try:
        Base.metadata.create_all(bind=engine)

        # Parche de migración en caliente
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE cheques ADD COLUMN estado VARCHAR DEFAULT 'Pendiente'"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE cambios_aceite ADD COLUMN qr_token VARCHAR"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE garantias_baterias ADD COLUMN qr_token VARCHAR"))
                conn.commit()
            except Exception:
                pass # Probablemente la columna ya exista
            try:
                conn.execute(text("ALTER TABLE ventas ADD COLUMN motivo_anulacion TEXT"))
                conn.commit()
            except Exception:
                pass

            try:
                conn.execute(text("CREATE TABLE IF NOT EXISTS vehiculos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER NOT NULL, dominio VARCHAR NOT NULL UNIQUE, marca VARCHAR, modelo VARCHAR, anio INTEGER)"))
                conn.execute(text("CREATE TABLE IF NOT EXISTS garantias_baterias (id INTEGER PRIMARY KEY AUTOINCREMENT, vehiculo_id INTEGER NOT NULL, producto_id INTEGER NOT NULL, fecha_instalacion DATE, meses_garantia INTEGER NOT NULL, fecha_vencimiento DATE NOT NULL, codigo_garantia VARCHAR NOT NULL UNIQUE)"))
                conn.execute(text("CREATE TABLE IF NOT EXISTS cambios_aceite (id INTEGER PRIMARY KEY AUTOINCREMENT, vehiculo_id INTEGER NOT NULL, fecha DATE, km_actual INTEGER NOT NULL, proximo_km INTEGER NOT NULL, aceite_utilizado VARCHAR NOT NULL, filtro_aceite BOOLEAN, filtro_aire BOOLEAN, filtro_combustible BOOLEAN, filtro_habitaculo BOOLEAN, observaciones VARCHAR)"))
                conn.execute(text("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, usuario TEXT UNIQUE, password TEXT, rol TEXT, permisos TEXT)"))
                conn.commit()
            except Exception:
                pass

            # Default admin
            try:
                from database.models.usuario import Usuario
                with get_session() as s:
                    count = s.query(Usuario).count()
                    if count == 0:
                        hashed = hashlib.sha256('admin'.encode()).hexdigest()
                        admin = Usuario(usuario='admin', password=hashed, rol='Administrador', permisos='TODOS')
                        s.add(admin)
                        s.commit()
            except Exception as e:
                print(e)

    except Exception as e:
        print(f"Error inicializando base de datos: {e}")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Login Modal
    from ui.login_dialog import LoginDialog
    login = LoginDialog()
    if login.exec() != LoginDialog.DialogCode.Accepted:
        sys.exit(0)

    permisos_usuario = login.get_permisos()
    rol_usuario = login.get_rol()

    window = MainWindow()
    window._aplicar_permisos(rol_usuario, permisos_usuario)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
