from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from bson import ObjectId
from bson.errors import InvalidId

from app.reservas.schemas import ReservaCreate, ReservaResponse, MiClaseActualResponse
from app.database import db
from app.usuarios.utils import obtener_usuario_actual, requerir_roles

router = APIRouter(prefix="/reservas", tags=["Reservas"])

coleccion_reservas = db["reservas"]
coleccion_espacios = db["espacios"]


def obtener_object_id(id_valor: str) -> ObjectId:
    try:
        return ObjectId(id_valor)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id del espacio enviado no tiene un formato válido de MongoDB",
        )


def convertir_reserva(documento: dict) -> dict:
    documento["id"] = str(documento["_id"])
    return documento


def convertir_espacio(documento: dict) -> dict:
    documento["id"] = str(documento["_id"])
    return documento


@router.get(
    "/mi-clase-actual",
    response_model=MiClaseActualResponse,
    summary="Consultar clase actual del docente",
)
async def obtener_mi_clase_actual(
    usuario_actual: dict = Depends(requerir_roles("Docente", "Admin")),
):
    """
    Retorna la clase actual del docente autenticado junto con el aula asignada.

    La búsqueda se realiza usando el nombre del docente almacenado en el token
    y el rango horario actual.
    """
    ahora = datetime.utcnow()
    nombre_docente = usuario_actual.get("nombre")

    reserva = await coleccion_reservas.find_one(
        {
            "docente": nombre_docente,
            "hora_inicio": {"$lte": ahora},
            "hora_fin": {"$gte": ahora},
        }
    )

    if not reserva:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró una clase activa para el docente autenticado",
        )

    espacio_object_id = obtener_object_id(reserva["espacio_id"])
    espacio = await coleccion_espacios.find_one({"_id": espacio_object_id})

    if not espacio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La clase actual está asociada a un espacio que no existe",
        )

    return {
        "reserva": convertir_reserva(reserva),
        "espacio": convertir_espacio(espacio),
    }


@router.post("/", response_model=ReservaResponse, status_code=status.HTTP_201_CREATED)
async def crear_reserva(
    reserva: ReservaCreate,
    usuario_actual: dict = Depends(obtener_usuario_actual),
):
    try:
        id_espacio_objeto = ObjectId(reserva.espacio_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id del espacio enviado no tiene un formato válido de MongoDB",
        )

    espacio_existe = await coleccion_espacios.find_one({"_id": id_espacio_objeto})

    if not espacio_existe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El espacio con ID '{reserva.espacio_id}' no existe",
        )

    if reserva.hora_fin <= reserva.hora_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La hora de fin debe ser posterior a la hora de inicio",
        )

    reserva_en_conflicto = await coleccion_reservas.find_one(
        {
            "espacio_id": reserva.espacio_id,
            "hora_inicio": {"$lt": reserva.hora_fin},
            "hora_fin": {"$gt": reserva.hora_inicio},
        }
    )

    if reserva_en_conflicto:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El espacio no está disponible en el horario seleccionado. Ya existe una reserva activa.",
        )

    nueva_reserva = reserva.model_dump()
    resultado = await coleccion_reservas.insert_one(nueva_reserva)

    reserva_guardada = await coleccion_reservas.find_one({"_id": resultado.inserted_id})

    if not reserva_guardada:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar la reserva",
        )

    return convertir_reserva(reserva_guardada)


@router.get("/", response_model=List[ReservaResponse])
async def listar_reservas():
    reservas = []
    cursor = coleccion_reservas.find()

    async for documento in cursor:
        reservas.append(convertir_reserva(documento))

    return reservas