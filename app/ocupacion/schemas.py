from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

# ENTIDAD OCUPACIÓN (Fase 1 — datos simulados, contrato listo para visión artificial)

TipoEspacio = Literal["library", "study_room", "computer_lab"]
EstadoOcupacion = Literal["Disponible", "Próximo", "Ocupado", "Sin datos"]


class EspacioOcupacion(BaseModel):
    id: str = Field(..., example="biblioteca-fica")
    name: str = Field(..., example="Biblioteca FICA")
    description: str = Field(..., example="Biblioteca de la Facultad de Ingeniería, Ciencias Físicas y Matemática.")
    type: TipoEspacio = Field(..., example="library")
    building: str = Field(..., example="Facultad de Ingeniería")
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
    source: Literal["mock"] = "mock"
    aiEnabled: bool = True
    detectionMethod: str = "mock_vision_ready"
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
