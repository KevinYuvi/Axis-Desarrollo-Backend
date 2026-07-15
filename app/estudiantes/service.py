from datetime import datetime
from typing import List, Optional

from app.estudiantes.schemas import ClaseEstudianteData, EdificioData


EDIFICIOS = {
    "edificio-ingenieria": {
        "id": "edificio-ingenieria",
        "nombre": "Facultad de Ingeniería",
        "bloque": "Bloque A",
        "referencia": "Entrada principal de la Facultad de Ingeniería.",
        "latitude": -0.1995,
        "longitude": -78.5042,
    },
    "edificio-tecnologico": {
        "id": "edificio-tecnologico",
        "nombre": "Edificio Tecnológico",
        "bloque": "Bloque T",
        "referencia": "Frente al patio central.",
        "latitude": -0.2010,
        "longitude": -78.5015,
    },
}


HORARIOS = [
    {
        "id": "clase-programacion-ii",
        "materia": "Programación II",
        "docente": "Ing. Carlos Pérez",
        "grupo": "Sexto A",
        "aula": "Aula 203",
        "edificio_id": "edificio-ingenieria",
        "dia_semana": "martes",
        "hora_inicio": "10:00",
        "hora_fin": "12:00",
    },
    {
        "id": "clase-base-datos",
        "materia": "Base de Datos",
        "docente": "Ing. María López",
        "grupo": "Sexto A",
        "aula": "Laboratorio 2",
        "edificio_id": "edificio-tecnologico",
        "dia_semana": "martes",
        "hora_inicio": "14:00",
        "hora_fin": "16:00",
    },
]


DIAS_SEMANA = {
    0: "lunes",
    1: "martes",
    2: "miércoles",
    3: "jueves",
    4: "viernes",
    5: "sábado",
    6: "domingo",
}


def _hora_a_minutos(hora: str) -> int:
    horas, minutos = hora.split(":")
    return int(horas) * 60 + int(minutos)


def _obtener_dia_actual() -> str:
    ahora = datetime.now()
    return DIAS_SEMANA[ahora.weekday()]


def _obtener_minutos_actuales() -> int:
    ahora = datetime.now()
    return ahora.hour * 60 + ahora.minute


def _calcular_estado_clase(hora_inicio: str, hora_fin: str) -> str:
    minutos_actuales = _obtener_minutos_actuales()
    inicio = _hora_a_minutos(hora_inicio)
    fin = _hora_a_minutos(hora_fin)

    if inicio <= minutos_actuales <= fin:
        return "actual"

    if minutos_actuales < inicio:
        return "proxima"

    return "finalizada"


def _construir_clase(raw: dict) -> Optional[ClaseEstudianteData]:
    edificio_raw = EDIFICIOS.get(raw["edificio_id"])

    if edificio_raw is None:
        return None

    edificio = EdificioData(**edificio_raw)

    return ClaseEstudianteData(
        id=raw["id"],
        materia=raw["materia"],
        docente=raw["docente"],
        grupo=raw["grupo"],
        aula=raw["aula"],
        edificio=edificio,
        dia_semana=raw["dia_semana"],
        hora_inicio=raw["hora_inicio"],
        hora_fin=raw["hora_fin"],
        estado=_calcular_estado_clase(raw["hora_inicio"], raw["hora_fin"]),
    )


async def get_mis_clases_hoy() -> List[ClaseEstudianteData]:
    dia_actual = _obtener_dia_actual()

    clases = []

    for item in HORARIOS:
        if item["dia_semana"] != dia_actual:
            continue

        clase = _construir_clase(item)

        if clase is not None:
            clases.append(clase)

    clases.sort(key=lambda item: _hora_a_minutos(item.hora_inicio))

    return clases


async def get_proxima_clase() -> Optional[ClaseEstudianteData]:
    clases_hoy = await get_mis_clases_hoy()

    candidatas = [
        clase
        for clase in clases_hoy
        if clase.estado in ("actual", "proxima")
    ]

    if not candidatas:
        return None

    candidatas.sort(key=lambda item: _hora_a_minutos(item.hora_inicio))

    return candidatas[0]