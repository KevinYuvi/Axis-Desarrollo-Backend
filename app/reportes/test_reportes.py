import pytest
from pydantic import ValidationError
from app.reportes.schemas import ReporteCreate, ReporteResponse


def test_crear_reporte_valido():
    """ReporteCreate solo modela la ENTRADA: sin estado ni fecha (los pone el router)."""
    reporte = ReporteCreate(
        espacio_id="665f1a2b3c4d5e6f7a8b9c0d",
        descripcion="El proyector no enciende desde la mañana",
        gravedad="media",
    )
    assert reporte.gravedad == "media"
    assert reporte.recurso_afectado == "General"


def test_crear_reporte_gravedad_invalida():
    with pytest.raises(ValidationError):
        ReporteCreate(espacio_id="x", descripcion="descripcion valida larga", gravedad="urgente")


def test_response_incluye_codigo_y_estado():
    r = ReporteResponse(
        id="1", espacio_id="e1", descripcion="Pizarra rota en el aula",
        gravedad="alta", recurso_afectado="Pizarra", codigo="TK-007",
        fecha_reporte="2026-07-09T10:00:00", estado="abierto",
    )
    assert r.codigo == "TK-007"
    assert r.estado == "abierto"
