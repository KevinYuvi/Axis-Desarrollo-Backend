from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ReporteCreate(BaseModel):
    espacio_id: str = Field(
        ...,
        example="6a4d3cf5bc6390c0b207e0c8",
        description="ID del espacio afectado",
    )

    descripcion: str = Field(
        ...,
        min_length=10,
        max_length=500,
        example="El proyector del laboratorio no enciende.",
    )

    gravedad: Literal["baja", "media", "alta"] = Field(
        ...,
        example="media",
    )

    # Recurso puntual afectado dentro del espacio (Proyector, Pizarra, etc.)
    recurso_afectado: str = Field(default="General", max_length=100)


class ReporteResponse(BaseModel):
    id: str

    espacio_id: str
    espacio_nombre: Optional[str] = None
    espacio_bloque: Optional[str] = None

    descripcion: str
    gravedad: Literal["baja", "media", "alta"]

    # Campos de ticket (Figma): recurso afectado y código secuencial TK-xxx
    recurso_afectado: str = "General"
    codigo: Optional[str] = None

    fecha_reporte: datetime
    estado: Literal["abierto", "en_proceso", "resuelto"]

    usuario_id: Optional[str] = None
    docente_nombre: Optional[str] = None

    class Config:
        from_attributes = True