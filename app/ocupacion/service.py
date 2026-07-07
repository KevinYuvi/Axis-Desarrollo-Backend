from datetime import datetime, timezone
from typing import List, Optional

from app.ocupacion import vision_client
from app.ocupacion.mock_data import RAW_SPACES, SPACE_VISION_SOURCES
from app.ocupacion.schemas import EspacioOcupacion


def _calculate_status(occupancy_percent: Optional[int]) -> str:
    """
    Calcula el estado de ocupación basado en el porcentaje actual.
    
    @param occupancy_percent: Porcentaje de ocupación del espacio
    @return string: Estado calculado (Disponible, Próximo, Ocupado, Sin datos)
    """
    if occupancy_percent is None:
        return "Sin datos"
    if occupancy_percent >= 90:
        return "Ocupado"
    if occupancy_percent >= 70:
        return "Próximo"
    return "Disponible"


def _build_reason(raw_space_data: dict, status: str) -> str:
    """
    Construye la razón o mensaje explicativo para la recomendación del espacio.
    
    @param raw_space_data: Diccionario con los datos en crudo del espacio
    @param status: Estado calculado del espacio
    @return string: Mensaje explicativo de la recomendación
    """
    if status == "Disponible":
        return (
            f"Tiene {raw_space_data['freeSeats']} puestos libres, "
            f"{raw_space_data['computersAvailable']} computadoras disponibles "
            f"y está a {raw_space_data['distanceMinutes']} min."
        )
    if status == "Próximo":
        return "Se está llenando rápido; considera otra opción si necesitas espacio de inmediato."
    if status == "Ocupado":
        return "Actualmente no tiene espacio disponible."
    return "Aún no hay datos de ocupación para este espacio."


def _to_occupancy_space(raw_space_data: dict) -> EspacioOcupacion:
    """
    Convierte un diccionario de datos en crudo al esquema de EspacioOcupacion.
    
    @param raw_space_data: Diccionario con los datos en crudo del espacio
    @return EspacioOcupacion: Objeto de esquema Pydantic para el espacio
    """
    status = _calculate_status(raw_space_data["occupancyPercent"])
    return EspacioOcupacion(
        **raw_space_data,
        status=status,
        updatedAt=datetime.now(timezone.utc),
        source="mock",
        aiEnabled=True,
        detectionMethod="mock_vision_ready",
        recommendationReason=_build_reason(raw_space_data, status),
    )


def get_spaces() -> List[EspacioOcupacion]:
    """
    Retorna el listado completo de espacios de estudio.
    
    @return List[EspacioOcupacion]: Lista de espacios de ocupación
    """
    return [_to_occupancy_space(raw) for raw in RAW_SPACES]


def get_space_by_id(space_id: str) -> Optional[EspacioOcupacion]:
    """
    Obtiene el detalle de un espacio específico mediante su identificador.
    
    @param space_id: Identificador único del espacio
    @return Optional[EspacioOcupacion]: Detalle del espacio o None si no existe
    """
    raw_space_data = next((r for r in RAW_SPACES if r["id"] == space_id), None)
    return _to_occupancy_space(raw_space_data) if raw_space_data else None


def get_recommendation() -> Optional[dict]:
    """
    Genera y retorna el mejor espacio recomendado para estudiar.
    La lógica filtra espacios ocupados o sin datos y ordena por ocupación y distancia.
    
    @return Optional[dict]: Diccionario con la recomendación generada o None si no hay candidatos
    """
    candidates = [
        space
        for space in get_spaces()
        if space.status not in ("Ocupado", "Sin datos")
    ]

    if not candidates:
        return None

    candidates.sort(key=lambda e: (e.occupancyPercent, e.distanceMinutes))
    best_candidate = candidates[0]

    reason = (
        f"Te recomendamos {best_candidate.name} porque tiene {best_candidate.freeSeats} puestos libres, "
        f"{best_candidate.computersAvailable} computadoras disponibles y está a {best_candidate.distanceMinutes} minutos."
    )
    confidence = round(max(0.5, min(0.99, 1 - (best_candidate.occupancyPercent / 100) * 0.6)), 2)

    return {"space": best_candidate, "reason": reason, "confidence": confidence}


def _build_vision_analyze_payload(space: EspacioOcupacion, space_id: str) -> Optional[dict]:
    """
    Construye el payload que se envía al vision-service para un espacio,
    usando la fuente de imagen/video configurada en SPACE_VISION_SOURCES.

    @param space: espacio base con los datos estáticos de Fase 1
    @param space_id: identificador del espacio
    @return: payload listo para POST /vision/analyze, o None si el espacio no tiene fuente configurada
    """
    vision_source = SPACE_VISION_SOURCES.get(space_id)
    if vision_source is None:
        return None

    return {
        "spaceId": space_id,
        "spaceName": space.name,
        "totalSeats": space.totalSeats,
        "computersTotal": space.computersTotal,
        "sourceType": vision_source["sourceType"],
        "sourcePath": vision_source["sourcePath"],
    }


def _merge_vision_result_into_space(base_space: EspacioOcupacion, vision_data: dict) -> EspacioOcupacion:
    """
    Combina el resultado del vision-service sobre el espacio base de Fase 1,
    conservando los campos que el vision-service no conoce (edificio, piso,
    salas de estudio, distancia, etc.) y actualizando solo las métricas de
    ocupación calculadas mediante visión artificial.

    @param base_space: espacio base con los datos estáticos de Fase 1
    @param vision_data: diccionario "data" devuelto por el vision-service
    @return: espacio actualizado con el mismo contrato de EspacioOcupacion
    """
    status = vision_data["status"]
    recommendation_reason = _build_reason(
        {
            "freeSeats": vision_data["freeSeats"],
            "computersAvailable": vision_data["computersAvailable"],
            "distanceMinutes": base_space.distanceMinutes,
        },
        status,
    )

    return base_space.model_copy(update={
        "occupiedSeats": vision_data["occupiedSeats"],
        "freeSeats": vision_data["freeSeats"],
        "computersAvailable": vision_data["computersAvailable"],
        "occupancyPercent": vision_data["occupancyPercent"],
        "status": status,
        "updatedAt": datetime.now(timezone.utc),
        "source": vision_data["source"],
        "detectionMethod": vision_data["detectionMethod"],
        "recommendationReason": recommendation_reason,
    })


async def analyze_space_with_vision(space_id: str) -> Optional[dict]:
    """
    Analiza un espacio consultando al vision-service. Si el vision-service no
    responde (apagado, timeout, error), cae de vuelta a los datos mock de
    Fase 1 sin romper la petición del usuario.

    @param space_id: identificador del espacio a analizar
    @return: {"space": EspacioOcupacion, "usedFallback": bool}, o None si el espacio no existe
    """
    base_space = get_space_by_id(space_id)
    if base_space is None:
        return None

    analyze_payload = _build_vision_analyze_payload(base_space, space_id)
    vision_data = await vision_client.request_analysis(analyze_payload) if analyze_payload else None

    if vision_data is None:
        return {"space": base_space, "usedFallback": True}

    updated_space = _merge_vision_result_into_space(base_space, vision_data)
    return {"space": updated_space, "usedFallback": False}
