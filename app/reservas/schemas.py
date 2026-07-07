from datetime import datetime
from pydantic import BaseModel, Field

from app.espacios.schemas import EspacioResponse


class ReservaBase(BaseModel):
    espacio_id: str = Field(
        ...,
        example="649c12a3f1234567890abcdef",
        description="ID del espacio reservado",
    )
    materia: str = Field(..., min_length=3, max_length=100, example="Programación Móvil")
    docente: str = Field(..., min_length=3, max_length=100, example="Ing. Juan Pérez")
    hora_inicio: datetime = Field(..., example="2026-06-29T07:00:00")
    hora_fin: datetime = Field(..., example="2026-06-29T09:00:00")


class ReservaCreate(ReservaBase):
    pass


class ReservaResponse(ReservaBase):
    id: str = Field(..., example="649c55b9f1234567890fbcde")

    class Config:
        from_attributes = True


class MiClaseActualResponse(BaseModel):
    reserva: ReservaResponse
    espacio: EspacioResponse