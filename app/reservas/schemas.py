from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

from app.espacios.schemas import EspacioResponse


class ReservaBase(BaseModel):
    espacio_id: str = Field(
        ...,
        example="649c12a3f1234567890abcdef",
        description="ID del espacio reservado",
    )

    materia: str = Field(
        ...,
        min_length=3,
        max_length=100,
        example="Programación Móvil",
    )

    hora_inicio: datetime = Field(
        ...,
        example="2026-07-07T08:00:00",
    )

    hora_fin: datetime = Field(
        ...,
        example="2026-07-07T10:00:00",
    )


class ReservaCreate(ReservaBase):
    pass


class ReservaResponse(ReservaBase):
    id: str = Field(
        ...,
        example="649c55b9f1234567890fbcde",
    )

    usuario_id: str = Field(
        ...,
        example="user_3GFlbkGBIjZnvpWneJjyoKKjzAX",
        description="ID del docente en Clerk",
    )

    docente_nombre: Optional[str] = Field(
        None,
        example="Ing. Juan Pérez",
    )

    class Config:
        from_attributes = True


class MiClaseActualResponse(BaseModel):
    reserva: Optional[ReservaResponse] = None
    espacio: Optional[EspacioResponse] = None