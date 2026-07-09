from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

# ENTIDAD ESPACIO 
class EspacioBase(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=100, example="Laboratorio de Computación 3")
    bloque: str = Field(..., min_length=1, max_length=50, example="Bloque B")
    tipo: Literal["aula", "laboratorio", "biblioteca", "auditorio"] = Field(..., example="laboratorio")
    capacidad: int = Field(..., gt=0, example=30)
    equipamiento: List[str] = Field(default=[], example=["30 PCs", "Proyector"])
    estado_actual: Literal["disponible", "ocupado", "mantenimiento"] = Field(default="disponible", example="disponible")
    
    # NUEVOS CAMPOS PARA EL MAPA INTERACTIVO (FASE 3 Y 4)
    coordenadas_gps: Optional[str] = Field(None, example="-0.198333, -78.503333", description="Coordenadas para Google Maps")
    svg_id: Optional[str] = Field(None, example="poly_lab_compu_3", description="ID del polígono interactivo en el plano SVG de MazeMap/Figma")

class EspacioCreate(EspacioBase):
    pass

class EspacioUpdate(BaseModel):
    """Actualización parcial de un espacio (solo Gestor)."""
    nombre: Optional[str] = Field(default=None, min_length=3, max_length=100)
    capacidad: Optional[int] = Field(default=None, gt=0)
    equipamiento: Optional[List[str]] = None
    estado_actual: Optional[Literal["disponible", "ocupado", "mantenimiento"]] = None
    coordenadas_gps: Optional[str] = None
    svg_id: Optional[str] = None

class EspacioResponse(EspacioBase):
    id: str = Field(..., example="649c12a3f1234567890abcdef")

    class Config:
        from_attributes = True