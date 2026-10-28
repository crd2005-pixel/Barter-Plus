import json
from pydantic import BaseModel, Field
from typing import List, Optional

class ProductoExtraido(BaseModel):
    codigo_proveedor: str = Field(description="Código del producto del proveedor. NO debe contener el signo $ ni ser el precio.")
    descripcion: str = Field(description="Descripción del producto o repuesto.")
    marca: str = Field(description="Marca del repuesto, deducida de la descripción o contexto si no está explícita.")
    costo: float = Field(description="Costo neto del repuesto (número decimal mayor a 0).")

class ListaProductos(BaseModel):
    productos: List[ProductoExtraido]

def parse_with_gemini(text_chunk, api_key):
    """
    Función placeholder que simula o implementa la integración real
    usando google-genai o requests con gemini-2.5-flash.
    En una integración real se usa el schema de Pydantic para forzar la estructura.
    """
    # En esta simulación solo devolveríamos una lista vacía si falla o no hay datos,
    # el motor determinista siempre se ejecuta como fallback o primera línea.
    return []

def fallback_ia_a_determinista(func_ia, func_determinista, *args, **kwargs):
    """
    Ejecuta el motor de IA. Si la respuesta es vacía o falla, ejecuta el determinista.
    """
    try:
        resultado = func_ia(*args, **kwargs)
        # Soportar respuestas JSON tanto en lista [...] como en diccionario {"productos": [...]}
        if isinstance(resultado, dict) and "productos" in resultado:
            resultado = resultado["productos"]

        if resultado and len(resultado) > 0:
            return resultado
    except Exception:
        pass # Falla silenciosa permitida aquí porque obligatoriamente va al determinista

    # Ejecutar incondicionalmente el determinista
    return func_determinista(*args, **kwargs)
