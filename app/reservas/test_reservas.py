import pytest
from pydantic import ValidationError
from app.reservas.schemas import ReservaCreate

def test_crear_reserva_valida():
    datos = {
        "espacio_id": "649c12a3f1234567890abcdef",
        "materia": "Programación Móvil",
        "docente": "Ing. Juan Pérez",
        "hora_inicio": "2026-06-29T07:00:00",
        "hora_fin": "2026-06-29T09:00:00"
    }
    reserva = ReservaCreate(**datos)
    assert reserva.materia == "Programación Móvil"

def test_crear_reserva_nombre_materia_corto():
    datos = {
        "espacio_id": "649c12a3f1234567890abcdef",
        "materia": "PR",
        "docente": "Ing. Juan Pérez",
        "hora_inicio": "2026-06-29T07:00:00",
        "hora_fin": "2026-06-29T09:00:00"
    }
    with pytest.raises(ValidationError):
        ReservaCreate(**datos)
