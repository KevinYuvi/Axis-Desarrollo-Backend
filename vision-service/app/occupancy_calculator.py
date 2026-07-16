from datetime import datetime, timezone
from typing import Optional

from app import config, detector
from app.schemas import AnalyzeData, AnalyzeRequest


def _calculate_occupancy_status(occupancy_percent: Optional[int]) -> str:
    if occupancy_percent is None:
        return "Sin datos"

    if occupancy_percent >= 90:
        return "Ocupado"

    if occupancy_percent >= 70:
        return "Próximo"

    return "Disponible"


def _calculate_occupancy_percent(occupied_seats: int, total_seats: int) -> Optional[int]:
    if total_seats <= 0:
        return None

    return round((occupied_seats / total_seats) * 100)


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


def _detect_people_count(source_type: str, source_path: str) -> Optional[int]:
    if source_type == "ip_camera_snapshot":
        return detector.count_people_in_ip_camera_snapshot(source_path)

    resolved_path = config.SERVICE_ROOT_DIR / source_path

    if not resolved_path.exists():
        return None

    if source_type == "sample_video":
        return detector.count_people_in_video(resolved_path)

    return detector.count_people_in_image(resolved_path)


def _get_detection_method(source_type: str, people_count: Optional[int]) -> str:
    if people_count is None:
        if source_type == "ip_camera_snapshot":
            return "camera_unreachable_or_yolo_failed"

        return "sample_not_found_or_yolo_failed"

    if source_type == "ip_camera_snapshot":
        return "yolo_ip_camera_snapshot"

    if source_type == "sample_video":
        return "yolo_local_sample_video"

    return "yolo_local_sample_image"


def analyze_space(request: AnalyzeRequest) -> AnalyzeData:
    """
    Analiza un espacio usando únicamente fuente real configurada.

    No usa mock.
    No usa fallback.
    No simula personas.

    Si la cámara o YOLO fallan, devuelve estado "Sin datos".
    """

    people_count = _detect_people_count(
        source_type=request.sourceType,
        source_path=request.sourcePath,
    )

    detection_method = _get_detection_method(
        source_type=request.sourceType,
        people_count=people_count,
    )

    if people_count is None:
        return AnalyzeData(
            spaceId=request.spaceId,
            spaceName=request.spaceName,
            peopleCount=0,
            totalSeats=request.totalSeats,
            occupiedSeats=0,
            freeSeats=0,
            computersTotal=request.computersTotal,
            computersAvailable=0,
            occupancyPercent=None,
            status="Sin datos",
            source="vision-service-fallback",
            detectionMethod=detection_method,
            aiEnabled=True,
            updatedAt=datetime.now(timezone.utc),
        )

    occupied_seats = people_count
    free_seats = max(request.totalSeats - occupied_seats, 0)

    occupancy_percent = _calculate_occupancy_percent(
        occupied_seats=occupied_seats,
        total_seats=request.totalSeats,
    )

    status = _calculate_occupancy_status(occupancy_percent)

    computers_available = _estimate_available_computers(
        computers_total=request.computersTotal,
        occupancy_percent=occupancy_percent,
    )

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
        source="vision-service",
        detectionMethod=detection_method,
        aiEnabled=True,
        updatedAt=datetime.now(timezone.utc),
    )


def to_latest_analysis_item(stored_analysis: dict) -> dict:
    return {
        "spaceId": stored_analysis["spaceId"],
        "personCount": stored_analysis["peopleCount"],
        "freeSeats": stored_analysis["freeSeats"],
        "occupancyPercentage": stored_analysis["occupancyPercent"],
        "status": stored_analysis["status"],
        "analyzedAt": stored_analysis["updatedAt"],
        "source": stored_analysis["source"],
    }