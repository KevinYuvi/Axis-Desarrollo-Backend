from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

# ENTIDAD DE ANÁLISIS DE VISIÓN (Fase 2 — imagen/video local de prueba)

SourceType = Literal["sample_image", "sample_video", "ip_camera_snapshot"]
VisionSource = Literal["vision-service", "vision-service-fallback"]
OccupancyStatus = Literal["Disponible", "Próximo", "Ocupado", "Sin datos"]


class AnalyzeRequest(BaseModel):
    spaceId: str = Field(..., example="biblioteca-fica")
    spaceName: str = Field(..., example="Biblioteca FICA")
    totalSeats: int = Field(..., ge=0, example=40)
    computersTotal: int = Field(..., ge=0, example=12)
    sourceType: SourceType = Field(..., example="sample_image")
    sourcePath: str = Field(..., example="samples/BIBLIO1.jpg")


class AnalyzeData(BaseModel):
    spaceId: str
    spaceName: str
    peopleCount: int
    totalSeats: int
    occupiedSeats: int
    freeSeats: int
    computersTotal: int
    computersAvailable: int
    occupancyPercent: int | None
    status: OccupancyStatus
    source: VisionSource
    detectionMethod: str
    aiEnabled: bool = True
    updatedAt: datetime


class AnalyzeResponse(BaseModel):
    ok: bool
    message: str
    data: AnalyzeData


class VisionErrorResponse(BaseModel):
    ok: bool = False
    message: str


class LatestAnalysisItem(BaseModel):
    """Entrada de GET /vision/latest — el último análisis en memoria de un espacio."""

    spaceId: str
    personCount: int
    freeSeats: int
    occupancyPercentage: Optional[int]
    status: OccupancyStatus
    analyzedAt: datetime
    # No estaba en el contrato pedido para esta fase, pero sin este campo el
    # frontend perdería la etiqueta "Fuente: Visión IA / Simulado" de Fase 2.
    source: VisionSource


class HealthResponse(BaseModel):
    ok: bool
    service: str
    status: str
