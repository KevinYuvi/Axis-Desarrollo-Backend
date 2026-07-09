from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
from app.espacios.schemas import EspacioResponse


class ReservaBase(BaseModel):
    espacio_id: str = Field(
        ...,
        example="649c12a3f1234567890abcdef",
        description="ID del espacio reservado (Laboratorio o Aula)",
    )
    materia: str = Field(..., min_length=3, max_length=100, example="Programación Móvil")
    hora_inicio: datetime = Field(..., example="2026-07-07T08:00:00")
    hora_fin: datetime = Field(..., example="2026-07-07T10:00:00")


class ReservaCreate(ReservaBase):
    # Ya no pedimos el campo "docente" aquí, la petición HTTP solo envía espacio, materia y horas.
    pass


class ReservaResponse(ReservaBase):
    id: str = Field(..., example="649c55b9f1234567890fbcde")
    # 🔑 Agregamos el ID del usuario real que es dueño de esta reserva
    usuario_id: str = Field(..., example="649b99a3f1234567890abcde", description="ID del docente en el sistema")
    # Opcional: Si quieres seguir devolviendo el nombre plano del docente para simplificar el Front, lo dejas como opcional
    docente_nombre: Optional[str] = Field(None, example="Ing. Juan Pérez")
    # Check-in de clase (Ayudante/Docente): confirma asistencia para que el aula no se libere
    checkin: bool = Field(default=False, description="Indica si ya se registró el check-in de la clase")
    checkin_hora: Optional[datetime] = Field(None, example="2026-07-07T08:05:00", description="Hora (Ecuador) en que se registró el check-in")

    class Config:
        from_attributes = True


class MiClaseActualResponse(BaseModel):
    reserva: ReservaResponse
    espacio: EspacioResponse