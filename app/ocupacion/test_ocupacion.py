import asyncio

import pytest

from app.ocupacion import service, vision_client


@pytest.fixture(autouse=True)
def stub_vision_service_unreachable(monkeypatch):
    """
    Evita que los tests hagan una llamada de red real al vision-service
    (lento e impredecible si no está corriendo). Los tests que necesitan
    simular una respuesta real la sobreescriben explícitamente.
    """
    async def fake_get_latest_snapshots():
        return []

    monkeypatch.setattr(vision_client, "get_latest_snapshots", fake_get_latest_snapshots)


EXPECTED_SPACE_IDS = {
    "biblioteca-fica",
    "biblioteca-general",
    "sala-grupal-2",
    "laboratorio-computadoras",
    "sala-lectura-humanidades",
}


def test_get_spaces_incluye_los_cinco_espacios_base():
    spaces = asyncio.run(service.get_spaces())
    assert {space.id for space in spaces} == EXPECTED_SPACE_IDS


def test_get_space_by_id_existente():
    space = asyncio.run(service.get_space_by_id("biblioteca-fica"))
    assert space is not None
    assert space.status == "Disponible"


def test_get_space_by_id_inexistente_devuelve_none():
    assert asyncio.run(service.get_space_by_id("no-existe")) is None


def test_regla_estado_ocupado_por_encima_de_90():
    space = asyncio.run(service.get_space_by_id("laboratorio-computadoras"))
    assert space.occupancyPercent == 97
    assert space.status == "Ocupado"


def test_regla_estado_proximo_entre_70_y_90():
    space = asyncio.run(service.get_space_by_id("biblioteca-general"))
    assert space.occupancyPercent == 82
    assert space.status == "Próximo"


def test_regla_estado_disponible_por_debajo_de_70():
    space = asyncio.run(service.get_space_by_id("sala-grupal-2"))
    assert space.occupancyPercent == 25
    assert space.status == "Disponible"


def test_regla_estado_sin_datos_cuando_occupancy_percent_es_none():
    space = asyncio.run(service.get_space_by_id("sala-lectura-humanidades"))
    assert space.occupancyPercent is None
    assert space.status == "Sin datos"


def test_recomendacion_excluye_ocupados_y_sin_datos():
    recommendation = asyncio.run(service.get_recommendation())
    assert recommendation is not None
    assert recommendation["space"].status not in ("Ocupado", "Sin datos")


def test_recomendacion_elige_menor_occupancy_percent():
    # Candidatos válidos: biblioteca-fica (45%), biblioteca-general (82%), sala-grupal-2 (25%)
    recommendation = asyncio.run(service.get_recommendation())
    assert recommendation["space"].id == "sala-grupal-2"
    assert 0 <= recommendation["confidence"] <= 1


# --- Fase 3: fusión con el último análisis automático del vision-service ---

LATEST_SNAPSHOT_FOR_FICA = {
    "spaceId": "biblioteca-fica",
    "personCount": 10,
    "freeSeats": 30,
    "occupancyPercentage": 25,
    "status": "Disponible",
    "analyzedAt": "2026-01-01T00:00:00+00:00",
    "source": "vision-service",
}


def test_get_spaces_sin_vision_service_usa_mock_de_fase_1(monkeypatch):
    async def fake_get_latest_snapshots():
        return []

    monkeypatch.setattr(vision_client, "get_latest_snapshots", fake_get_latest_snapshots)

    spaces = asyncio.run(service.get_spaces())
    fica = next(space for space in spaces if space.id == "biblioteca-fica")

    assert fica.source == "mock"
    assert fica.occupancyPercent == 45


def test_get_spaces_con_snapshot_del_vision_service_actualiza_metricas(monkeypatch):
    async def fake_get_latest_snapshots():
        return [LATEST_SNAPSHOT_FOR_FICA]

    monkeypatch.setattr(vision_client, "get_latest_snapshots", fake_get_latest_snapshots)

    spaces = asyncio.run(service.get_spaces())
    fica = next(space for space in spaces if space.id == "biblioteca-fica")

    assert fica.source == "vision-service"
    assert fica.occupancyPercent == 25
    assert fica.status == "Disponible"
    assert fica.freeSeats == 30
    # Los campos estáticos que el vision-service no conoce se conservan
    assert fica.building == "Facultad de Ingeniería"

    # El resto de espacios sin snapshot todavía conservan el mock de Fase 1
    general = next(space for space in spaces if space.id == "biblioteca-general")
    assert general.source == "mock"


def test_get_space_by_id_inexistente_no_consulta_al_vision_service(monkeypatch):
    vision_service_called = False

    async def fake_get_latest_snapshots():
        nonlocal vision_service_called
        vision_service_called = True
        return []

    monkeypatch.setattr(vision_client, "get_latest_snapshots", fake_get_latest_snapshots)

    result = asyncio.run(service.get_space_by_id("no-existe"))

    assert result is None
    assert vision_service_called is False
