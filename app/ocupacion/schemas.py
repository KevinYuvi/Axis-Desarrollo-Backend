from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

# ENTIDAD OCUPACIÓN — contrato de datos del módulo de ocupación por visión artificial

TipoEspacio = Literal["library", "study_room", "computer_lab"]
EstadoOcupacion = Literal["Disponible", "Próximo", "Ocupado", "Sin datos"]


class EspacioOcupacion(BaseModel):
    id: str = Field(..., example="biblioteca-cisco")
    name: str = Field(..., example="Biblioteca Cisco")
    description: str = Field(..., example="Biblioteca Cisco de la Universidad Central.")
    type: TipoEspacio = Field(..., example="library")
    building: str = Field(..., example="Universidad Central")
    floor: str = Field(..., example="Planta Baja")
    totalSeats: int = Field(..., ge=0, example=40)
    occupiedSeats: int = Field(..., ge=0, example=18)
    freeSeats: int = Field(..., ge=0, example=22)
    computersTotal: int = Field(..., ge=0, example=12)
    computersAvailable: int = Field(..., ge=0, example=5)
    studyRoomsTotal: int = Field(..., ge=0, example=3)
    studyRoomsAvailable: int = Field(..., ge=0, example=2)
    distanceMinutes: int = Field(..., ge=0, example=5)
    occupancyPercent: Optional[int] = Field(default=None, ge=0, le=100, example=45)
    status: EstadoOcupacion = Field(..., example="Disponible")
    updatedAt: datetime
    latitude: Optional[float] = Field(default=None, example=-0.1995)
    longitude: Optional[float] = Field(default=None, example=-78.5042)
    source: Literal["vision-service", "vision-service-fallback"] = "vision-service"
    aiEnabled: bool = True
    detectionMethod: str = "vision_scheduler_latest"
    recommendationReason: Optional[str] = None


class RecomendacionData(BaseModel):
    space: EspacioOcupacion
    reason: str
    confidence: float


class OcupacionListResponse(BaseModel):
    ok: bool
    message: str
    data: List[EspacioOcupacion]


class OcupacionDetailResponse(BaseModel):
    ok: bool
    message: str
    data: EspacioOcupacion


class OcupacionRecomendacionResponse(BaseModel):
    ok: bool
    message: str
    data: RecomendacionData


class OcupacionErrorResponse(BaseModel):
    ok: bool = False
    message: str
