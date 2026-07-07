import asyncio

from app.ocupacion import service, vision_client

EXPECTED_SPACE_IDS = {
    "biblioteca-fica",
    "biblioteca-general",
    "sala-grupal-2",
    "laboratorio-computadoras",
    "sala-lectura-humanidades",
}


def test_get_spaces_incluye_los_cinco_espacios_base():
    spaces = service.get_spaces()
    assert {space.id for space in spaces} == EXPECTED_SPACE_IDS


def test_get_space_by_id_existente():
    space = service.get_space_by_id("biblioteca-fica")
    assert space is not None
    assert space.status == "Disponible"


def test_get_space_by_id_inexistente_devuelve_none():
    assert service.get_space_by_id("no-existe") is None


def test_regla_estado_ocupado_por_encima_de_90():
    space = service.get_space_by_id("laboratorio-computadoras")
    assert space.occupancyPercent == 97
    assert space.status == "Ocupado"


def test_regla_estado_proximo_entre_70_y_90():
    space = service.get_space_by_id("biblioteca-general")
    assert space.occupancyPercent == 82
    assert space.status == "Próximo"


def test_regla_estado_disponible_por_debajo_de_70():
    space = service.get_space_by_id("sala-grupal-2")
    assert space.occupancyPercent == 25
    assert space.status == "Disponible"


def test_regla_estado_sin_datos_cuando_occupancy_percent_es_none():
    space = service.get_space_by_id("sala-lectura-humanidades")
    assert space.occupancyPercent is None
    assert space.status == "Sin datos"


def test_recomendacion_excluye_ocupados_y_sin_datos():
    recommendation = service.get_recommendation()
    assert recommendation is not None
    assert recommendation["space"].status not in ("Ocupado", "Sin datos")


def test_recomendacion_elige_menor_occupancy_percent():
    # Candidatos válidos: biblioteca-fica (45%), biblioteca-general (82%), sala-grupal-2 (25%)
    recommendation = service.get_recommendation()
    assert recommendation["space"].id == "sala-grupal-2"
    assert 0 <= recommendation["confidence"] <= 1


# --- Fase 2: análisis mediante vision-service (con monkeypatch, sin red real) ---

VISION_SUCCESS_RESPONSE = {
    "spaceId": "biblioteca-fica",
    "spaceName": "Biblioteca FICA",
    "peopleCount": 10,
    "totalSeats": 40,
    "occupiedSeats": 10,
    "freeSeats": 30,
    "computersTotal": 12,
    "computersAvailable": 9,
    "occupancyPercent": 25,
    "status": "Disponible",
    "source": "vision-service",
    "detectionMethod": "yolo_local_sample",
    "aiEnabled": True,
    "updatedAt": "2026-01-01T00:00:00+00:00",
}


def test_analyze_space_with_vision_espacio_inexistente_devuelve_none():
    result = asyncio.run(service.analyze_space_with_vision("no-existe"))
    assert result is None


def test_analyze_space_with_vision_exito_actualiza_metricas(monkeypatch):
    async def fake_request_analysis(payload):
        assert payload["spaceId"] == "biblioteca-fica"
        return VISION_SUCCESS_RESPONSE

    monkeypatch.setattr(vision_client, "request_analysis", fake_request_analysis)

    result = asyncio.run(service.analyze_space_with_vision("biblioteca-fica"))

    assert result["usedFallback"] is False
    assert result["space"].occupancyPercent == 25
    assert result["space"].status == "Disponible"
    assert result["space"].source == "vision-service"
    # Los campos que el vision-service no conoce se conservan del mock de Fase 1
    assert result["space"].building == "Facultad de Ingeniería"


def test_analyze_space_with_vision_sin_respuesta_usa_fallback_de_fase_1(monkeypatch):
    async def fake_request_analysis(payload):
        return None

    monkeypatch.setattr(vision_client, "request_analysis", fake_request_analysis)

    result = asyncio.run(service.analyze_space_with_vision("biblioteca-fica"))

    assert result["usedFallback"] is True
    assert result["space"].source == "mock"
    assert result["space"].occupancyPercent == 45
