from datetime import datetime, timezone
from typing import List, Optional

from app.ocupacion import vision_client
from app.ocupacion.mock_data import RAW_SPACES
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


def _estimate_available_computers(computers_total: int, occupancy_percent: Optional[int]) -> int:
    """
    Estima proporcionalmente cuántas computadoras están libres según la
    ocupación medida por el vision-service (espejo de la misma fórmula que
    usa el vision-service, ya que GET /vision/latest no incluye este dato).

    @param computers_total: cantidad total de computadoras del espacio
    @param occupancy_percent: porcentaje de ocupación medido (puede ser None)
    @return: cantidad estimada de computadoras disponibles
    """
    if computers_total <= 0:
        return 0

    occupancy_ratio = (occupancy_percent or 0) / 100
    estimated_available = round(computers_total * (1 - occupancy_ratio))
    return max(0, min(computers_total, estimated_available))


def _apply_latest_vision_snapshot(base_space: EspacioOcupacion, snapshot: dict) -> EspacioOcupacion:
    """
    Superpone el último análisis automático del vision-service (Fase 3) sobre
    el espacio base de Fase 1, conservando los campos estáticos que el
    vision-service no conoce (edificio, piso, salas de estudio, distancia, etc.).

    @param base_space: espacio base con los datos estáticos de Fase 1
    @param snapshot: entrada de GET /vision/latest para este espacio
    @return: espacio con las métricas de ocupación actualizadas
    """
    status = snapshot["status"]
    occupied_seats = snapshot["personCount"]
    free_seats = snapshot["freeSeats"]
    occupancy_percent = snapshot["occupancyPercentage"]
    computers_available = _estimate_available_computers(base_space.computersTotal, occupancy_percent)

    recommendation_reason = _build_reason(
        {
            "freeSeats": free_seats,
            "computersAvailable": computers_available,
            "distanceMinutes": base_space.distanceMinutes,
        },
        status,
    )

    return base_space.model_copy(update={
        "occupiedSeats": occupied_seats,
        "freeSeats": free_seats,
        "computersAvailable": computers_available,
        "occupancyPercent": occupancy_percent,
        "status": status,
        "updatedAt": snapshot["analyzedAt"],
        "source": snapshot["source"],
        "detectionMethod": "vision_scheduler_latest",
        "recommendationReason": recommendation_reason,
    })


async def _with_latest_vision_snapshots(spaces: List[EspacioOcupacion]) -> List[EspacioOcupacion]:
    """
    Combina espacios base de Fase 1 con los últimos análisis automáticos del
    vision-service (Fase 3). Si el vision-service no responde, devuelve los
    espacios base sin cambios — el fallback de Fase 1 sigue funcionando igual.

    @param spaces: espacios base de Fase 1
    @return: espacios con las métricas más recientes superpuestas cuando existan
    """
    latest_snapshots = await vision_client.get_latest_snapshots()
    if not latest_snapshots:
        return spaces

    snapshots_by_space_id = {snapshot["spaceId"]: snapshot for snapshot in latest_snapshots}
    return [
        _apply_latest_vision_snapshot(space, snapshots_by_space_id[space.id])
        if space.id in snapshots_by_space_id
        else space
        for space in spaces
    ]


async def get_spaces() -> List[EspacioOcupacion]:
    """
    Retorna el listado completo de espacios de estudio, combinado con el
    último análisis automático del vision-service cuando esté disponible.

    @return List[EspacioOcupacion]: Lista de espacios de ocupación
    """
    base_spaces = [_to_occupancy_space(raw) for raw in RAW_SPACES]
    return await _with_latest_vision_snapshots(base_spaces)


async def get_space_by_id(space_id: str) -> Optional[EspacioOcupacion]:
    """
    Obtiene el detalle de un espacio específico, combinado con el último
    análisis automático del vision-service cuando esté disponible.

    @param space_id: Identificador único del espacio
    @return Optional[EspacioOcupacion]: Detalle del espacio o None si no existe
    """
    raw_space_data = next((r for r in RAW_SPACES if r["id"] == space_id), None)
    if raw_space_data is None:
        return None

    base_space = _to_occupancy_space(raw_space_data)
    updated_spaces = await _with_latest_vision_snapshots([base_space])
    return updated_spaces[0]


async def get_recommendation() -> Optional[dict]:
    """
    Genera y retorna el mejor espacio recomendado para estudiar, ya
    considerando las métricas más recientes del vision-service.
    La lógica filtra espacios ocupados o sin datos y ordena por ocupación y distancia.

    @return Optional[dict]: Diccionario con la recomendación generada o None si no hay candidatos
    """
    candidates = [
        space
        for space in await get_spaces()
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
