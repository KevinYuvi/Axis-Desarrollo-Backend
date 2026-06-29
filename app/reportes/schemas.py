from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Literal

# ENTIDAD REPORTE / INCIDENCIAS

class ReporteBase(BaseModel):
    espacio_id: str = Field(..., example="649c12a3f1234567890abcdef", description="ID del espacio afectado")
    descripcion: str = Field(..., min_length=10, max_length=500, example="El proyector del laboratorio parpadea y no da video.")
    gravedad: Literal["baja", "media", "alta"] = Field(..., example="media")
    fecha_reporte: datetime = Field(default_factory=datetime.utcnow)
    estado: Literal["abierto", "en_proceso", "resuelto"] = Field(default="abierto")

class ReporteCreate(ReporteBase):
    pass

class ReporteResponse(ReporteBase):
    id: str = Field(..., example="649c66a1f1234567890edcba")
    

    class Config:
        from_attributes = True