from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from bson import ObjectId
from bson.errors import InvalidId

from app.espacios.schemas import EspacioCreate, EspacioResponse
from app.database import db
from app.usuarios.utils import requerir_roles

router = APIRouter(prefix="/espacios", tags=["Espacios"])

coleccion_espacios = db["espacios"]


def convertir_espacio(documento: dict) -> dict:
    """Convierte el documento de MongoDB a un formato compatible con Pydantic."""
    documento["id"] = str(documento["_id"])
    return documento


def obtener_object_id(id_valor: str) -> ObjectId:
    """Valida y convierte un string a ObjectId de MongoDB."""
    try:
        return ObjectId(id_valor)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id del espacio enviado no tiene un formato válido de MongoDB",
        )


@router.post("/", response_model=EspacioResponse, status_code=status.HTTP_201_CREATED)
async def crear_espacio(espacio: EspacioCreate):
    nuevo_espacio = espacio.model_dump()

    resultado = await coleccion_espacios.insert_one(nuevo_espacio)

    espacio_guardado = await coleccion_espacios.find_one({"_id": resultado.inserted_id})

    if not espacio_guardado:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar el espacio en la base de datos",
        )

    return convertir_espacio(espacio_guardado)


@router.get("/", response_model=List[EspacioResponse])
async def listar_espacios():
    espacios = []
    cursor = coleccion_espacios.find()

    async for documento in cursor:
        espacios.append(convertir_espacio(documento))

    return espacios


@router.get(
    "/estado-actual",
    response_model=List[EspacioResponse],
    summary="Consultar estado actual de espacios",
)
async def obtener_estado_actual(
    usuario_actual: dict = Depends(requerir_roles("Estudiante", "Docente", "Admin"))
):
    """
    Retorna la lista de espacios con su estado actual.

    Esta ruta alimenta el mapa interactivo del estudiante y permite visualizar
    disponibilidad general sin modificar datos.
    """
    espacios = []
    cursor = coleccion_espacios.find()

    async for documento in cursor:
        espacios.append(convertir_espacio(documento))

    return espacios


@router.patch(
    "/{espacio_id}/liberar",
    response_model=EspacioResponse,
    summary="Liberar un espacio académico",
)
async def liberar_espacio(
    espacio_id: str,
    usuario_actual: dict = Depends(requerir_roles("Docente", "Admin")),
):
    """
    Permite que un Docente o Admin marque un aula como disponible.

    Esta acción se usa cuando el docente termina la clase antes de tiempo.
    """
    espacio_object_id = obtener_object_id(espacio_id)

    espacio_existe = await coleccion_espacios.find_one({"_id": espacio_object_id})

    if not espacio_existe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El espacio con ID '{espacio_id}' no existe",
        )

    await coleccion_espacios.update_one(
        {"_id": espacio_object_id},
        {"$set": {"estado_actual": "disponible"}},
    )

    espacio_actualizado = await coleccion_espacios.find_one({"_id": espacio_object_id})

    if not espacio_actualizado:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al liberar el espacio",
        )

    return convertir_espacio(espacio_actualizado)


@router.get(
    "/{espacio_id}",
    response_model=EspacioResponse,
    summary="Consultar detalle de un espacio",
)
async def obtener_detalle_espacio(
    espacio_id: str,
    usuario_actual: dict = Depends(requerir_roles("Estudiante", "Docente", "Admin")),
):
    """
    Retorna la ficha técnica de un aula o laboratorio específico.
    """
    espacio_object_id = obtener_object_id(espacio_id)

    espacio = await coleccion_espacios.find_one({"_id": espacio_object_id})

    if not espacio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El espacio con ID '{espacio_id}' no existe",
        )

    return convertir_espacio(espacio)