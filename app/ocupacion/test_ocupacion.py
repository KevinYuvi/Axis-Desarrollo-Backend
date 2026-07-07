from app.ocupacion import service

IDS_ESPERADOS = {
    "biblioteca-fica",
    "biblioteca-general",
    "sala-grupal-2",
    "laboratorio-computadoras",
    "sala-lectura-humanidades",
}


def test_listar_espacios_incluye_los_cinco_espacios_base():
    espacios = service.listar_espacios()
    assert {e.id for e in espacios} == IDS_ESPERADOS


def test_obtener_espacio_existente():
    espacio = service.obtener_espacio("biblioteca-fica")
    assert espacio is not None
    assert espacio.status == "Disponible"


def test_obtener_espacio_inexistente_devuelve_none():
    assert service.obtener_espacio("no-existe") is None


def test_regla_estado_ocupado_por_encima_de_90():
    espacio = service.obtener_espacio("laboratorio-computadoras")
    assert espacio.occupancyPercent == 97
    assert espacio.status == "Ocupado"


def test_regla_estado_proximo_entre_70_y_90():
    espacio = service.obtener_espacio("biblioteca-general")
    assert espacio.occupancyPercent == 82
    assert espacio.status == "Próximo"


def test_regla_estado_disponible_por_debajo_de_70():
    espacio = service.obtener_espacio("sala-grupal-2")
    assert espacio.occupancyPercent == 25
    assert espacio.status == "Disponible"


def test_regla_estado_sin_datos_cuando_occupancy_percent_es_none():
    espacio = service.obtener_espacio("sala-lectura-humanidades")
    assert espacio.occupancyPercent is None
    assert espacio.status == "Sin datos"


def test_recomendacion_excluye_ocupados_y_sin_datos():
    recomendacion = service.obtener_recomendacion()
    assert recomendacion is not None
    assert recomendacion["space"].status not in ("Ocupado", "Sin datos")


def test_recomendacion_elige_menor_occupancy_percent():
    # Candidatos válidos: biblioteca-fica (45%), biblioteca-general (82%), sala-grupal-2 (25%)
    recomendacion = service.obtener_recomendacion()
    assert recomendacion["space"].id == "sala-grupal-2"
    assert 0 <= recomendacion["confidence"] <= 1
