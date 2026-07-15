from typing import List, Optional
from pydantic import BaseModel


class EdificioData(BaseModel):
    id: str
    nombre: str
    bloque: Optional[str] = None
    referencia: Optional[str] = None
    latitude: float
    longitude: float


class ClaseEstudianteData(BaseModel):
    id: str
    materia: str
    docente: str
    grupo: str
    aula: str
    edificio: EdificioData
    dia_semana: str
    hora_inicio: str
    hora_fin: str
    estado: str


class ClasesHoyResponse(BaseModel):
    ok: bool
    message: str
    data: List[ClaseEstudianteData]


class ProximaClaseResponse(BaseModel):
    ok: bool
    message: str
    data: Optional[ClaseEstudianteData]