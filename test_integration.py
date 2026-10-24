import sys
sys.path.append('.')
from unificador_listas.app import _process_table_row

def test():
    # Test La Casa de las Baterias
    row_baterias = [
        "M22ED\nLP 670\nDL 620\nBP 620 (6meses)\nUB 620",
        "12X65\n12X65\n12X65\n12X65\n12X65",
        "WILLARD\nMOURA\nLEMOM\nPREMIUM\nSEINECA",
        "ford k fiesta - ecosport - agile - fiorino",
        "$\n$ 113.873\n$ 71.187\n$ 60.500\n$ 55.000\n$ 45.000"
    ]
    extracted, _ = _process_table_row(row_baterias, "BAT", "BATERIAS", 0)
    print(extracted)
    assert len(extracted) == 5
    assert extracted[0]['codigo_proveedor'] == 'M22ED'
    assert extracted[0]['marca'] == 'WILLARD'
    assert extracted[0]['costo_neto'] == 113873.0

    # Test Seineca
    row_seineca = [
        "SFF32205",
        "AA1482/1 E F. AIRE VW AMAROK",
        "WK6002\n$ 12.272",
        "MANN1",
        "FRAM1",
        "",
        "MARENO1"
    ]
    extracted, _ = _process_table_row(row_seineca, "SEINECA", "FILTROS", 0)
    print(extracted)
    assert len(extracted) == 1
    assert extracted[0]['codigo_proveedor'] == 'SFF32205'
    assert extracted[0]['costo_neto'] == 12272.0
    assert "WK6002" in extracted[0]['descripcion']
    assert "MANN1" in extracted[0]['descripcion']

    print("All integration tests passed!")

if __name__ == "__main__":
    test()
