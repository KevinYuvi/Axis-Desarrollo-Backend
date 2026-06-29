from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Literal

# ENTIDAD ESPACIO 

class EspacioBase(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=100, example="Laboratorio de Computación 3")
    bloque: str = Field(..., min_length=1, max_length=50, example="Bloque B")
    tipo: Literal["aula", "laboratorio"] = Field(..., example="laboratorio")
    capacidad: int = Field(..., gt=0, example=30)
    equipamiento: List[str] = Field(default=[], example=["30 PCs", "Proyector"])
    estado_actual: Literal["disponible", "ocupado", "mantenimiento"] = Field(default="disponible", example="disponible")

class EspacioCreate(EspacioBase):
    pass

class EspacioResponse(EspacioBase):
    id: str = Field(..., example="649c12a3f1234567890abcdef")

    class Config:
        from_attributes = True



# ENTIDAD RESERVA 

class ReservaBase(BaseModel):
    # Relación lógica con el espacio mediante su ID en MongoDB (string)
    espacio_id: str = Field(..., example="649c12a3f1234567890abcdef", description="ID del espacio reservado")
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


# ENTIDAD REPORTE / INCIDENCIAS

class ReporteBase(BaseModel):
    espacio_id: str = Field(..., example="649c12a3f1234567890abcdef", description="ID del espacio afectado")
    descripcion: str = Field(..., min_length=10, max_length=500, example="El proyector del laboratorio parpadea y no da video.")
    gravedad: Literal["baja", "media", "alta"] = Field(..., example="media")
    fecha_reporte: datetime = Field(default_factory=datetime.utcnow)

class ReporteCreate(ReporteBase):
    pass

class ReporteResponse(ReporteBase):
    id: str = Field(..., example="649c66a1f1234567890edcba")
    estado: Literal["abierto", "en_proceso", "resuelto"] = Field(default="abierto")

    class Config:
        from_attributes = True