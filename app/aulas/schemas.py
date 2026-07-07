# Importamos BaseModel para crear modelos de validación de datos
from pydantic import BaseModel, Field

# Enum permite definir valores fijos
from enum import Enum

# Optional permite campos opcionales
from typing import Optional, List


# Estados posibles de un aula
class EstadoAulaEnum(str, Enum):
    DISPONIBLE = "Disponible"
    OCUPADA = "Ocupada"
    BLOQUEADA = "Bloqueada"
    MANTENIMIENTO = "Mantenimiento"


# Modelo para crear un aula
class AulaCreate(BaseModel):
    nombre: str
    edificio: str
    planta: str
    capacidad: int = Field(..., gt=0)
    recursos: List[str] = []
    estado: EstadoAulaEnum = EstadoAulaEnum.DISPONIBLE


# Modelo de respuesta al consultar aulas
class AulaResponse(BaseModel):
    id: str
    nombre: str
    edificio: str
    planta: str
    capacidad: int
    recursos: List[str]
    estado: EstadoAulaEnum
    motivo_bloqueo: Optional[str] = None


# Modelo para actualizar el estado del aula
class AulaEstadoUpdate(BaseModel):
    estado: EstadoAulaEnum
    motivo_bloqueo: Optional[str] = None