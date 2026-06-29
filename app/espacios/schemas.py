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

