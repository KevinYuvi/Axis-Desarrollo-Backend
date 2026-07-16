from pydantic import BaseModel, Field
from typing import List, Literal


TipoEspacio = Literal[
    "aula",
    "laboratorio",
    "biblioteca",
    "auditorio",
    "sala",
]

EstadoEspacio = Literal[
    "disponible",
    "ocupado",
    "mantenimiento",
]


class EspacioBase(BaseModel):
    nombre: str = Field(
        ...,
        min_length=3,
        max_length=100,
        example="Laboratorio de Computación 3",
    )

    bloque: str = Field(
        default="Sin bloque",
        min_length=1,
        max_length=100,
        example="Bloque B",
    )

    tipo: TipoEspacio = Field(
        ...,
        example="laboratorio",
    )

    capacidad: int = Field(
        ...,
        gt=0,
        example=30,
    )

    equipamiento: List[str] = Field(
        default_factory=list,
        example=["30 PCs", "Proyector"],
    )

    estado_actual: EstadoEspacio = Field(
        default="disponible",
        example="disponible",
    )


class EspacioCreate(EspacioBase):
    pass


class EspacioResponse(EspacioBase):
    id: str = Field(..., example="649c12a3f1234567890abcdef")

    class Config:
        from_attributes = True