from typing import List, Optional

from app.ocupacion import vision_client
from app.ocupacion.schemas import EspacioOcupacion


# Metadatos estáticos del espacio monitoreado por cámara. La clave debe
# coincidir con el "spaceId" registrado en vision-service/app/space_registry.py
# y con LIVE_CAMERA_SPACE_ID del frontend, para que estadísticas, frame
# anotado y stream en vivo apunten al mismo espacio físico.
STATIC_SPACE_METADATA = {
    "biblioteca-cisco": {
        "name": "Biblioteca Cisco",
        "description": "Biblioteca Cisco de la Universidad Central.",
        "type": "library",
        "building": "Universidad Central",
        "floor": "Planta Baja",
        "totalSeats": 40,
        "computersTotal": 12,
        "studyRoomsTotal": 3,
        "studyRoomsAvailable": 2,
        "distanceMinutes": 5,
        # Coordenadas GPS de la biblioteca dentro del campus; las usa el
        # frontend para el botón "Ver ubicación" (mapa y ruta en Google Maps).
        "latitude": -0.198310,
        "longitude": -78.503950,
    },
}


def _estimate_available_computers(
    computers_total: int,
    occupancy_percent: Optional[int],
) -> int:
    if computers_total <= 0:
        return 0

    if occupancy_percent is None:
        return 0

    occupancy_ratio = occupancy_percent / 100
    estimated_available = round(computers_total * (1 - occupancy_ratio))

    return max(0, min(computers_total, estimated_available))


def _build_reason(space: EspacioOcupacion) -> str:
    if space.status == "Disponible":
        return (
            f"Tiene {space.freeSeats} puestos libres, "
            f"{space.computersAvailable} computadoras disponibles "
            f"y está a {space.distanceMinutes} min."
        )

    if space.status == "Próximo":
        return "Se está llenando rápido; considera otra opción si necesitas espacio de inmediato."

    if space.status == "Ocupado":
        return "Actualmente no tiene espacio disponible."

    return "Aún no hay datos de ocupación para este espacio."


def _snapshot_to_space(snapshot: dict) -> Optional[EspacioOcupacion]:
    space_id = snapshot.get("spaceId")

    metadata = STATIC_SPACE_METADATA.get(space_id)

    if metadata is None:
        return None

    occupancy_percent = snapshot.get("occupancyPercentage")
    occupied_seats = snapshot.get("personCount", 0)
    free_seats = snapshot.get("freeSeats", 0)

    computers_total = metadata["computersTotal"]

    computers_available = _estimate_available_computers(
        computers_total=computers_total,
        occupancy_percent=occupancy_percent,
    )

    space = EspacioOcupacion(
        id=space_id,
        name=metadata["name"],
        description=metadata["description"],
        type=metadata["type"],
        building=metadata["building"],
        floor=metadata["floor"],
        totalSeats=metadata["totalSeats"],
        occupiedSeats=occupied_seats,
        freeSeats=free_seats,
        computersTotal=computers_total,
        computersAvailable=computers_available,
        studyRoomsTotal=metadata["studyRoomsTotal"],
        studyRoomsAvailable=metadata["studyRoomsAvailable"],
        distanceMinutes=metadata["distanceMinutes"],
        occupancyPercent=occupancy_percent,
        status=snapshot.get("status", "Sin datos"),
        updatedAt=snapshot.get("analyzedAt"),
        latitude=metadata["latitude"],
        longitude=metadata["longitude"],
        source=snapshot.get("source", "vision-service-fallback"),
        aiEnabled=True,
        detectionMethod="vision_scheduler_latest",
        recommendationReason=None,
    )

    return space.model_copy(
        update={
            "recommendationReason": _build_reason(space),
        }
    )


async def get_spaces() -> List[EspacioOcupacion]:
    """
    Retorna los espacios monitoreados según el último análisis del
    vision-service, enriquecidos con los metadatos estáticos de cada espacio.
    """

    latest_snapshots = await vision_client.get_latest_snapshots()

    spaces = []

    for snapshot in latest_snapshots:
        space = _snapshot_to_space(snapshot)

        if space is not None:
            spaces.append(space)

    return spaces


async def get_space_by_id(space_id: str) -> Optional[EspacioOcupacion]:
    spaces = await get_spaces()

    return next((space for space in spaces if space.id == space_id), None)


async def get_recommendation() -> Optional[dict]:
    candidates = [
        space
        for space in await get_spaces()
        if space.status not in ("Ocupado", "Sin datos")
        and space.occupancyPercent is not None
    ]

    if not candidates:
        return None

    candidates.sort(key=lambda e: (e.occupancyPercent, e.distanceMinutes))

    best_candidate = candidates[0]

    reason = (
        f"Te recomendamos {best_candidate.name} porque tiene "
        f"{best_candidate.freeSeats} puestos libres, "
        f"{best_candidate.computersAvailable} computadoras disponibles "
        f"y está a {best_candidate.distanceMinutes} minutos."
    )

    confidence = round(
        max(0.5, min(0.99, 1 - (best_candidate.occupancyPercent / 100) * 0.6)),
        2,
    )

    return {
        "space": best_candidate,
        "reason": reason,
        "confidence": confidence,
    }