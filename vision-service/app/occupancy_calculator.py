from datetime import datetime, timezone
from typing import Optional

from app import config, detector
from app.schemas import AnalyzeData, AnalyzeRequest


def _calculate_occupancy_status(occupancy_percent: Optional[int]) -> str:
    """
    Calcula el estado de ocupación a partir del porcentaje, con los mismos
    umbrales que usa el backend principal (Fase 1) para que ambos contratos
    sean compatibles.

    @param occupancy_percent: porcentaje de ocupación calculado, o None si no aplica
    @return: estado textual (Disponible, Próximo, Ocupado, Sin datos)
    """
    if occupancy_percent is None:
        return "Sin datos"
    if occupancy_percent >= 90:
        return "Ocupado"
    if occupancy_percent >= 70:
        return "Próximo"
    return "Disponible"


def _calculate_occupancy_percent(occupied_seats: int, total_seats: int) -> Optional[int]:
    """
    Calcula el porcentaje de ocupación protegiendo la división por cero.

    @param occupied_seats: puestos ocupados detectados
    @param total_seats: capacidad total del espacio
    @return: porcentaje redondeado, o None si el espacio no tiene puestos definidos
    """
    if total_seats <= 0:
        return None
    return round((occupied_seats / total_seats) * 100)


def _estimate_available_computers(computers_total: int, occupancy_percent: Optional[int]) -> int:
    """
    Estima proporcionalmente cuántas computadoras están libres según la
    ocupación general del espacio (no hay detección real de computadoras en esta fase).

    @param computers_total: cantidad total de computadoras del espacio
    @param occupancy_percent: porcentaje de ocupación calculado (puede ser None)
    @return: cantidad estimada de computadoras disponibles
    """
    if computers_total <= 0:
        return 0

    occupancy_ratio = (occupancy_percent or 0) / 100
    estimated_available = round(computers_total * (1 - occupancy_ratio))
    return max(0, min(computers_total, estimated_available))


def _simulate_people_count(total_seats: int) -> int:
    """
    Genera un conteo de personas simulado y determinístico para el modo
    fallback (sin archivo de muestra o sin modelo YOLO disponible).

    @param total_seats: capacidad total del espacio
    @return: cantidad simulada de personas ocupando el espacio
    """
    return round(total_seats * config.FALLBACK_OCCUPANCY_RATIO)


def _detect_people_count(source_type: str, resolved_path) -> Optional[int]:
    """
    Ejecuta la detección real (imagen o video) delegando en el detector.

    @param source_type: "sample_image" o "sample_video"
    @param resolved_path: ruta absoluta ya resuelta del archivo de muestra
    @return: cantidad de personas detectadas, o None si no fue posible detectar
    """
    if source_type == "sample_video":
        return detector.count_people_in_video(resolved_path)
    return detector.count_people_in_image(resolved_path)


def analyze_space(request: AnalyzeRequest) -> AnalyzeData:
    """
    Analiza un espacio a partir de una imagen/video local de prueba y devuelve
    las métricas de ocupación en el mismo contrato que usa el backend principal.
    Nunca lanza por archivo faltante o modelo no disponible: degrada al modo
    fallback simulado para no romper la cadena backend -> vision-service.

    @param request: payload recibido en POST /vision/analyze
    @return: datos de ocupación calculados, listos para responder al backend principal
    """
    if request.sourceType == "ip_camera_snapshot":
        people_count = detector.count_people_in_ip_camera_snapshot(request.sourcePath)
        detection_method = (
            "yolo_ip_camera_snapshot" if people_count is not None else "fallback_camera_unreachable"
        )
    else:
        resolved_path = config.SERVICE_ROOT_DIR / request.sourcePath
        people_count = None
        detection_method = "fallback_no_sample"

        if resolved_path.exists():
            people_count = _detect_people_count(request.sourceType, resolved_path)
            detection_method = (
                "yolo_local_sample_video" if request.sourceType == "sample_video" else "yolo_local_sample"
            )
            if people_count is None:
                detection_method = "fallback_model_unavailable"

    if people_count is None:
        people_count = _simulate_people_count(request.totalSeats)
        source = "vision-service-fallback"
    else:
        source = "vision-service"

    occupied_seats = people_count
    free_seats = max(request.totalSeats - occupied_seats, 0)
    occupancy_percent = _calculate_occupancy_percent(occupied_seats, request.totalSeats)
    status = _calculate_occupancy_status(occupancy_percent)
    computers_available = _estimate_available_computers(request.computersTotal, occupancy_percent)

    return AnalyzeData(
        spaceId=request.spaceId,
        spaceName=request.spaceName,
        peopleCount=people_count,
        totalSeats=request.totalSeats,
        occupiedSeats=occupied_seats,
        freeSeats=free_seats,
        computersTotal=request.computersTotal,
        computersAvailable=computers_available,
        occupancyPercent=occupancy_percent,
        status=status,
        source=source,
        detectionMethod=detection_method,
        aiEnabled=True,
        updatedAt=datetime.now(timezone.utc),
    )


def to_latest_analysis_item(stored_analysis: dict) -> dict:
    """
    Convierte un análisis guardado (formato AnalyzeData serializado) al
    contrato más liviano que expone GET /vision/latest.

    @param stored_analysis: análisis tal como lo guardó el scheduler en el storage
    @return: diccionario listo para validar contra LatestAnalysisItem
    """
    return {
        "spaceId": stored_analysis["spaceId"],
        "personCount": stored_analysis["peopleCount"],
        "freeSeats": stored_analysis["freeSeats"],
        "occupancyPercentage": stored_analysis["occupancyPercent"],
        "status": stored_analysis["status"],
        "analyzedAt": stored_analysis["updatedAt"],
        "source": stored_analysis["source"],
    }
