from database.conexion import engine, Base, get_session
from database.models.producto import Producto
from services.producto_service import ProductoService
from services.venta_service import VentaService

def run_tests():
    print("--- Iniciando Pruebas de Servicios ---")

    # Asegurarnos de que las tablas existen
    Base.metadata.create_all(bind=engine)

    # a) Crear un producto de prueba con su costo
    print("\n[1] Creando producto de prueba...")
    producto = ProductoService.crear_producto(
        nombre="Aceite Sintético 5W40",
        costo=1000.0,
        iva=21.0,
        codigo_barras="1789228952",
        stock_inicial=50.0
    )
    print(f"Producto creado: {producto.nombre} | ID: {producto.id} | Costo: {producto.costo} | Stock: {producto.stock_actual}")

    # b) Simular una actualización de precio aplicando un margen (ej. 30%)
    print("\n[2] Actualizando precio con margen del 30%...")
    producto_actualizado = ProductoService.actualizar_precio(producto.id, margen=30.0)
    print(f"Precio actualizado: {producto_actualizado.precio_minorista}")

    # c) Simular una venta de ese producto (ej. venta de 2 unidades)
    print("\n[3] Simulando venta de 2 unidades...")
    detalles_venta = [
        {'producto_id': producto_actualizado.id, 'cantidad': 2.0, 'precio_unitario': producto_actualizado.precio_minorista}
    ]
    venta = VentaService.procesar_venta(detalles=detalles_venta, metodo_pago="Efectivo", monto_abonado=4000.0)
    print(f"Venta Procesada: ID {venta.id} | Total: {venta.total} | Vuelto: {venta.vuelto}")

    # d) Imprimir los resultados en la consola para verificar que el stock bajó
    print("\n[4] Verificando resultados finales...")
    with get_session() as session:
        producto_db = session.get(Producto, producto_actualizado.id)
        print(f"Stock Final del Producto '{producto_db.nombre}': {producto_db.stock_actual} (Debería ser 48.0)")

if __name__ == "__main__":
    run_tests()
