import pytest
from pydantic import ValidationError
from app.reportes.schemas import ReporteCreate

def test_crear_reporte_valido():
    datos = {
        "espacio_id": "649c12a3f1234567890abcdef",
        "descripcion": "El proyector del laboratorio parpadea y no da video.",
        "gravedad": "media"
    }
    reporte = ReporteCreate(**datos)
    assert reporte.gravedad == "media"
    assert reporte.estado == "abierto"  # Verifica estado por defecto
    assert reporte.fecha_reporte is not None

def test_crear_reporte_gravedad_invalida():
    datos = {
        "espacio_id": "649c12a3f1234567890abcdef",
        "descripcion": "Fallo total de las luces del aula.",
        "gravedad": "critica"  # Error: No pertenece a baja, media o alta
    }
    with pytest.raises(ValidationError):
        ReporteCreate(**datos)
