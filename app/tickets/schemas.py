from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from datetime import datetime


class PrioridadTicketEnum(str, Enum):
    BAJA = "Baja"
    MEDIA = "Media"
    ALTA = "Alta"
    CRITICA = "Crítica"


class EstadoTicketEnum(str, Enum):
    PENDIENTE = "Pendiente"
    EN_PROGRESO = "En progreso"
    RESUELTO = "Resuelto"
    BLOQUEADO = "Bloqueado"


class TicketCreate(BaseModel):
    aula_id: str
    aula_nombre: str
    recurso_afectado: str
    descripcion: str = Field(..., min_length=5)
    prioridad: PrioridadTicketEnum
    incidencia_id: Optional[str] = None


class TicketResponse(BaseModel):
    id: str
    codigo: str
    aula_id: str
    aula_nombre: str
    recurso_afectado: str
    descripcion: str
    prioridad: PrioridadTicketEnum
    estado: EstadoTicketEnum
    creado_por: str
    nombre_creador: str
    fecha_creacion: datetime
    incidencia_id: Optional[str] = None
    observacion_admin: Optional[str] = None


class TicketEstadoUpdate(BaseModel):
    estado: EstadoTicketEnum
    observacion_admin: Optional[str] = None