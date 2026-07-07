from datetime import datetime, timezone
from typing import List, Optional

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
