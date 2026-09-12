# Este archivo asegura que todos los modelos se registren en el Base de SQLAlchemy
# al importar el paquete de models.
from .producto import Categoria, Marca, Producto
from .proveedor import Proveedor, ProveedorCuentaCorriente
from .cliente import Cliente, ClienteCuentaCorriente
from .venta import Venta, DetalleVenta
from .caja import Caja, MovimientoCaja
from .contabilidad import AsientoDiario, LibroIVA, PedidoManual, GastoOperativo
from .taller import Vehiculo, GarantiaBateria, CambioAceite
