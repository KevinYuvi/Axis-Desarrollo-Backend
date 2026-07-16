from typing import List, Optional
from pydantic import BaseModel, Field


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


class ClaseActualResponse(BaseModel):
    ok: bool
    message: str
    data: Optional[ClaseEstudianteData]


class ClaseDetalleResponse(BaseModel):
    ok: bool
    message: str
    data: Optional[ClaseEstudianteData]


class ArchivoReporteData(BaseModel):
    nombre_original: Optional[str] = None
    filename: Optional[str] = None
    url: Optional[str] = None
    content_type: Optional[str] = None


class ReporteClaseActualData(BaseModel):
    id: str
    codigo: str
    materia: str
    aula: str
    edificio: EdificioData
    descripcion: str
    gravedad: str
    estado: str
    imagenes: List[ArchivoReporteData] = []


class ReporteClaseActualResponse(BaseModel):
    ok: bool
    message: str
    data: ReporteClaseActualData


class ReporteEstudianteData(BaseModel):
    id: str
    codigo: str
    materia: Optional[str] = None
    aula: Optional[str] = None
    espacio_nombre: Optional[str] = None
    descripcion: str
    gravedad: str
    estado: str
    fecha_reporte: Optional[str] = None
    imagenes: List[ArchivoReporteData] = []


class MisReportesResponse(BaseModel):
    ok: bool
    message: str
    data: List[ReporteEstudianteData]


class AsignarGrupoEstudianteCreate(BaseModel):
    grupo_id: str = Field(..., min_length=1)
    usuario_id: Optional[str] = None
    email: Optional[str] = None


class AsignacionEstudianteResponse(BaseModel):
    ok: bool
    message: str
    data: dict
