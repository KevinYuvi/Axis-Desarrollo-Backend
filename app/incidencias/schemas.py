# Importamos BaseModel para crear modelos de datos con Pydantic
from pydantic import BaseModel, Field

# Importamos Enum para definir opciones fijas, como prioridad y estado
from enum import Enum

# Optional permite que un campo pueda ser opcional o nulo
from typing import Optional

# datetime se usa para manejar fechas y horas
from datetime import datetime


# Enum para definir las prioridades permitidas de una incidencia
class PrioridadEnum(str, Enum):
    BAJA = "Baja"
    MEDIA = "Media"
    ALTA = "Alta"
    CRITICA = "Crítica"


# Enum para definir los estados permitidos de una incidencia
class EstadoIncidenciaEnum(str, Enum):
    PENDIENTE = "Pendiente"
    EN_PROGRESO = "En progreso"
    RESUELTA = "Resuelta"
    BLOQUEADA = "Bloqueada"


# Modelo que se usa cuando el ayudante crea una nueva incidencia
class IncidenciaCreate(BaseModel):
    # ID del aula donde ocurrió el problema
    aula_id: str

    # Nombre visible del aula
    aula_nombre: str

    # Recurso afectado, por ejemplo: Proyector, Pizarra, Computadora
    recurso_afectado: str

    # Prioridad de la incidencia: Baja, Media, Alta o Crítica
    prioridad: PrioridadEnum

    # Descripción del problema, mínimo 5 caracteres
    descripcion: str = Field(..., min_length=5)

    # URL de imagen opcional, por si luego agregan evidencia fotográfica
    imagen_url: Optional[str] = None


# Modelo que se devuelve como respuesta al consultar o crear una incidencia
class IncidenciaResponse(BaseModel):
    # ID generado por MongoDB convertido a texto
    id: str

    # ID del aula
    aula_id: str

    # Nombre del aula
    aula_nombre: str

    # Recurso afectado
    recurso_afectado: str

    # Prioridad de la incidencia
    prioridad: PrioridadEnum

    # Descripción del problema
    descripcion: str

    # Estado actual de la incidencia
    estado: EstadoIncidenciaEnum

    # Correo del usuario que creó la incidencia
    creado_por: str

    # Nombre del usuario que creó la incidencia
    nombre_creador: str

    # Fecha y hora en que se creó la incidencia
    fecha_creacion: datetime

    # Imagen opcional
    imagen_url: Optional[str] = None


# Modelo usado cuando el administrador actualiza el estado de una incidencia
class IncidenciaEstadoUpdate(BaseModel):
    # Nuevo estado de la incidencia
    estado: EstadoIncidenciaEnum