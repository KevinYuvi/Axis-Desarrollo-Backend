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
    
    # 🔴 CAMPOS CLAVE PARA EL MAPA Y EL SVG 
    coordenadas_gps: Optional[str] = Field(None, example="-0.198333, -78.503333", description="Coordenadas para el pin en OpenStreetMap")
    svg_id: Optional[str] = Field(None, example="aula_101", description="ID exacto del polígono en el archivo SVG de React Native")

class EspacioCreate(EspacioBase):
    pass

class EspacioResponse(EspacioBase):
    id: str = Field(..., example="649c12a3f1234567890abcdef")

    class Config:
        from_attributes = True