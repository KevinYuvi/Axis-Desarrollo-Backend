from datetime import datetime, time, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from bson.errors import InvalidId

from app.reservas.schemas import ReservaCreate, ReservaResponse, MiClaseActualResponse
from app.database import db
from app.usuarios.utils import requerir_roles

from app.realtime.manager import realtime_manager

router = APIRouter(prefix="/reservas", tags=["Reservas"])

coleccion_reservas = db["reservas"]
coleccion_espacios = db["espacios"]


def obtener_hora_ecuador() -> datetime:
    """
    Devuelve la hora actual de Ecuador como datetime sin timezone.
    Esto permite comparar correctamente con las fechas guardadas desde el front.
    """
    return datetime.utcnow() - timedelta(hours=5)


def obtener_object_id(id_valor: str) -> ObjectId:
    try:
        return ObjectId(id_valor)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id enviado no tiene un formato válido de MongoDB",
        )


def convertir_reserva(documento: dict) -> dict:
    documento["id"] = str(documento["_id"])
    documento.pop("_id", None)
    return documento


def convertir_espacio(documento: dict) -> dict:
    documento["id"] = str(documento["_id"])
    documento.pop("_id", None)
    return documento


def obtener_usuario_id(usuario_actual: dict) -> str:
    usuario_id = (
        usuario_actual.get("_id")
        or usuario_actual.get("id")
        or usuario_actual.get("sub")
    )

    if not usuario_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo determinar el ID del usuario desde el token",
        )

    return str(usuario_id)


def filtro_reservas_vigentes() -> dict:
    return {
        "estado": {
            "$nin": ["liberada", "cancelada"]
        },
        "liberada_anticipadamente": {
            "$ne": True
        },
    }


@router.get(
    "/mi-clase-actual",
    response_model=MiClaseActualResponse,
    summary="Consultar clase actual del docente",
)
async def obtener_mi_clase_actual(
    usuario_actual: dict = Depends(requerir_roles("Docente", "Admin")),
):
    usuario_id = obtener_usuario_id(usuario_actual)
    ahora = obtener_hora_ecuador()

    reserva = await coleccion_reservas.find_one(
        {
            "usuario_id": usuario_id,
            "hora_inicio": {"$lte": ahora},
            "hora_fin": {"$gte": ahora},
            **filtro_reservas_vigentes(),
        }
    )

    if not reserva:
        return {
            "reserva": None,
            "espacio": None,
        }

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


@router.get(
    "/mis-clases-hoy",
    response_model=List[dict],
    summary="Obtener todas las clases del docente programadas para el día de hoy",
)
async def obtener_mis_clases_hoy(
    usuario_actual: dict = Depends(requerir_roles("Docente", "Admin")),
):
    usuario_id = obtener_usuario_id(usuario_actual)
    ahora = obtener_hora_ecuador()

    inicio_dia = datetime.combine(ahora.date(), time.min)
    fin_dia = datetime.combine(ahora.date(), time.max)

    cursor = coleccion_reservas.find(
        {
            "usuario_id": usuario_id,
            "hora_inicio": {"$lt": fin_dia},
            "hora_fin": {"$gt": inicio_dia},
            **filtro_reservas_vigentes(),
        }
    ).sort("hora_inicio", 1)

    cronograma_hoy = []

    async for reserva in cursor:
        espacio = None

        if reserva.get("espacio_id"):
            try:
                espacio_object_id = obtener_object_id(reserva["espacio_id"])
                espacio = await coleccion_espacios.find_one({"_id": espacio_object_id})
            except HTTPException:
                espacio = None

        cronograma_hoy.append(
            {
                "reserva": convertir_reserva(reserva),
                "espacio": convertir_espacio(espacio) if espacio else None,
            }
        )

    return cronograma_hoy


@router.patch(
    "/liberar-actual",
    response_model=dict,
    summary="Liberar la clase actual del docente",
)
async def liberar_clase_actual(
    usuario_actual: dict = Depends(requerir_roles("Docente", "Admin")),
    ):
    usuario_id = obtener_usuario_id(usuario_actual)
    ahora = obtener_hora_ecuador()

    reserva = await coleccion_reservas.find_one(
        {
            "usuario_id": usuario_id,
            "hora_inicio": {"$lte": ahora},
            "hora_fin": {"$gte": ahora},
            **filtro_reservas_vigentes(),
        }
    )

    if not reserva:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tienes una clase activa para liberar en este momento.",
        )

    espacio_id = reserva.get("espacio_id")

    await coleccion_reservas.update_one(
        {"_id": reserva["_id"]},
        {
            "$set": {
                "estado": "liberada",
                "hora_fin": ahora,
                "liberada_anticipadamente": True,
                "liberada_en": ahora,
                "actualizado_en": ahora,
            }
        },
    )

    espacio_actualizado = None

    if espacio_id:
        try:
            espacio_object_id = obtener_object_id(espacio_id)

            await coleccion_espacios.update_one(
                {"_id": espacio_object_id},
                {"$set": {"estado_actual": "disponible"}},
            )

            espacio_actualizado = await coleccion_espacios.find_one(
                {"_id": espacio_object_id}
            )
        except HTTPException:
            espacio_actualizado = None

    reserva_actualizada = await coleccion_reservas.find_one(
        {"_id": reserva["_id"]}
    )

    await realtime_manager.emitir({
        "tipo": "reservas_actualizadas",
        "origen": "liberar_clase_actual",
    })

    await realtime_manager.emitir({
        "tipo": "aulas_actualizadas",
        "origen": "liberar_clase_actual",
    })

    await realtime_manager.emitir({
        "tipo": "dashboard_actualizado",
        "origen": "liberar_clase_actual",
    })

    return {
        "message": "Aula liberada correctamente.",
        "reserva": convertir_reserva(reserva_actualizada),
        "espacio": convertir_espacio(espacio_actualizado)
        if espacio_actualizado
        else None,
    }


@router.patch(
    "/{reserva_id}/liberar",
    response_model=dict,
    summary="Liberar una reserva futura o activa por ID",
)
async def liberar_reserva_por_id(
    reserva_id: str,
    usuario_actual: dict = Depends(requerir_roles("Docente", "Admin")),
    ):
    usuario_id = obtener_usuario_id(usuario_actual)
    ahora = obtener_hora_ecuador()

    reserva_object_id = obtener_object_id(reserva_id)

    reserva = await coleccion_reservas.find_one(
        {
            "_id": reserva_object_id,
            "usuario_id": usuario_id,
            **filtro_reservas_vigentes(),
        }
    )

    if not reserva:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró la reserva vigente o no pertenece al usuario actual.",
        )

    hora_fin = reserva.get("hora_fin")

    if hora_fin and hora_fin < ahora:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes liberar una reserva que ya finalizó.",
        )

    espacio_id = reserva.get("espacio_id")

    await coleccion_reservas.update_one(
        {"_id": reserva["_id"]},
        {
            "$set": {
                "estado": "liberada",
                "hora_fin": ahora,
                "liberada_anticipadamente": True,
                "liberada_en": ahora,
                "actualizado_en": ahora,
            }
        },
    )

    espacio_actualizado = None

    if espacio_id:
        try:
            espacio_object_id = obtener_object_id(espacio_id)

            await coleccion_espacios.update_one(
                {"_id": espacio_object_id},
                {"$set": {"estado_actual": "disponible"}},
            )

            espacio_actualizado = await coleccion_espacios.find_one(
                {"_id": espacio_object_id}
            )
        except HTTPException:
            espacio_actualizado = None

    reserva_actualizada = await coleccion_reservas.find_one(
        {"_id": reserva["_id"]}
    )

    await realtime_manager.emitir({
        "tipo": "reservas_actualizadas",
        "origen": "liberar_reserva",
    })

    await realtime_manager.emitir({
        "tipo": "aulas_actualizadas",
        "origen": "liberar_reserva",
    })

    await realtime_manager.emitir({
        "tipo": "dashboard_actualizado",
        "origen": "liberar_reserva",
    })

    return {
        "message": "Reserva liberada correctamente.",
        "reserva": convertir_reserva(reserva_actualizada),
        "espacio": convertir_espacio(espacio_actualizado)
        if espacio_actualizado
        else None,
    }


@router.post(
    "/",
    response_model=ReservaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva reserva",
)
async def crear_reserva(
    reserva: ReservaCreate,
    usuario_actual: dict = Depends(requerir_roles("Docente", "Admin")),
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
            **filtro_reservas_vigentes(),
        }
    )

    if reserva_en_conflicto:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El espacio no está disponible en el horario seleccionado. Ya existe una reserva activa.",
        )

    usuario_id = obtener_usuario_id(usuario_actual)
    ahora = obtener_hora_ecuador()

    nueva_reserva = reserva.model_dump()
    nueva_reserva["usuario_id"] = usuario_id
    nueva_reserva["docente_nombre"] = usuario_actual.get("nombre", "Docente AXIS")
    nueva_reserva["estado"] = "reservada"
    nueva_reserva["liberada_anticipadamente"] = False
    nueva_reserva["creada_en"] = ahora
    nueva_reserva["actualizado_en"] = ahora

    resultado = await coleccion_reservas.insert_one(nueva_reserva)

    reserva_guardada = await coleccion_reservas.find_one(
        {"_id": resultado.inserted_id}
    )

    if not reserva_guardada:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar la reserva",
        )

    await coleccion_espacios.update_one(
        {"_id": id_espacio_objeto},
        {
            "$set": {
                "estado_actual": "ocupado",
                "actualizado_en": ahora,
            }
        },
    )

    await realtime_manager.emitir({
        "tipo": "reservas_actualizadas",
        "origen": "crear_reserva",
    })

    await realtime_manager.emitir({
        "tipo": "dashboard_actualizado",
        "origen": "crear_reserva",
    })
    

    return convertir_reserva(reserva_guardada)


@router.get(
    "/",
    response_model=List[ReservaResponse],
    summary="Listar todas las reservas",
)
async def listar_reservas(
    usuario_actual: dict = Depends(requerir_roles("Admin")),
):
    reservas = []
    cursor = coleccion_reservas.find().sort("hora_inicio", 1)

    async for documento in cursor:
        reservas.append(convertir_reserva(documento))

    return reservas