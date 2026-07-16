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
    """
    return datetime.utcnow() - timedelta(hours=5)


def obtener_object_id(id_valor: str) -> ObjectId:
    try:
        return ObjectId(str(id_valor))
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id enviado no tiene un formato válido de MongoDB",
        )


def object_id_or_none(valor: str):
    try:
        return ObjectId(str(valor))
    except (InvalidId, TypeError):
        return None


def obtener_usuario_id(usuario_actual: dict) -> str:
    usuario_id = (
        usuario_actual.get("_id")
        or usuario_actual.get("id")
        or usuario_actual.get("user_id")
        or usuario_actual.get("sub")
    )

    if not usuario_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo determinar el ID del usuario desde el token",
        )

    return str(usuario_id)


def obtener_rol(usuario_actual: dict) -> str:
    return str(
        usuario_actual.get("rol")
        or usuario_actual.get("role")
        or ""
    ).strip().lower()


def filtro_reservas_vigentes() -> dict:
    return {
        "estado": {
            "$nin": ["liberada", "cancelada", "finalizada"]
        },
        "liberada_anticipadamente": {
            "$ne": True
        },
    }


def calcular_estado_tiempo_reserva(hora_inicio: datetime, hora_fin: datetime) -> str:
    ahora = obtener_hora_ecuador()

    if hora_inicio <= ahora <= hora_fin:
        return "activa"

    if ahora < hora_inicio:
        return "futura"

    return "finalizada"


def convertir_reserva(documento: dict) -> dict:
    data = dict(documento)
    data["id"] = str(data.get("_id"))
    data.pop("_id", None)
    return data


def convertir_espacio(documento: dict | None) -> dict | None:
    if not documento:
        return None

    data = dict(documento)
    data["id"] = str(data.get("_id") or data.get("id"))
    data.pop("_id", None)
    return data


async def obtener_espacio_por_reserva(reserva: dict) -> dict | None:
    espacio_id = str(reserva.get("espacio_id") or "")

    if not espacio_id:
        return None

    espacio_object_id = object_id_or_none(espacio_id)

    if espacio_object_id:
        espacio = await coleccion_espacios.find_one({"_id": espacio_object_id})
        if espacio:
            return espacio

    return await coleccion_espacios.find_one({"id": espacio_id})


async def convertir_reserva_completa(documento: dict) -> dict:
    reserva = convertir_reserva(documento)
    espacio = await obtener_espacio_por_reserva(documento)

    hora_inicio = reserva.get("hora_inicio")
    hora_fin = reserva.get("hora_fin")

    estado_tiempo = "sin_horario"

    if reserva.get("estado") == "liberada" or reserva.get("liberada_anticipadamente"):
        estado_tiempo = "liberada"
    elif reserva.get("estado") == "cancelada":
        estado_tiempo = "cancelada"
    elif hora_inicio and hora_fin:
        if hora_fin <= hora_inicio:
            estado_tiempo = "liberada"
        else:
            estado_tiempo = calcular_estado_tiempo_reserva(hora_inicio, hora_fin)

    if espacio:
        espacio_nombre = espacio.get("nombre", "Aula no registrada")
        espacio_bloque = espacio.get("bloque", "Sin bloque")
        ubicacion = (
            espacio.get("ubicacion")
            or espacio.get("referencia")
            or espacio.get("direccion")
            or espacio.get("bloque")
            or "Ubicación no registrada"
        )
        tipo = espacio.get("tipo")
        capacidad = espacio.get("capacidad")
        estado_actual = espacio.get("estado_actual")
    else:
        espacio_nombre = reserva.get("espacio_nombre", "Aula no registrada")
        espacio_bloque = reserva.get("espacio_bloque", "Sin bloque")
        ubicacion = reserva.get("ubicacion", "Ubicación no registrada")
        tipo = reserva.get("tipo")
        capacidad = reserva.get("capacidad")
        estado_actual = None

    reserva["espacio_nombre"] = espacio_nombre
    reserva["aula"] = espacio_nombre
    reserva["espacio_bloque"] = espacio_bloque
    reserva["bloque"] = espacio_bloque
    reserva["ubicacion"] = ubicacion
    reserva["tipo"] = tipo
    reserva["capacidad"] = capacidad
    reserva["estado_actual_espacio"] = estado_actual
    reserva["estado_tiempo"] = estado_tiempo
    reserva["espacio"] = convertir_espacio(espacio)

    return reserva


async def emitir_eventos_reservas(origen: str) -> None:
    await realtime_manager.emitir({
        "tipo": "reservas_actualizadas",
        "origen": origen,
    })

    await realtime_manager.emitir({
        "tipo": "aulas_actualizadas",
        "origen": origen,
    })

    await realtime_manager.emitir({
        "tipo": "dashboard_actualizado",
        "origen": origen,
    })


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

    espacio = await obtener_espacio_por_reserva(reserva)

    if not espacio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La clase actual está asociada a un espacio que no existe",
        )

    return {
        "reserva": await convertir_reserva_completa(reserva),
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
        espacio = await obtener_espacio_por_reserva(reserva)

        cronograma_hoy.append(
            {
                "reserva": await convertir_reserva_completa(reserva),
                "espacio": convertir_espacio(espacio),
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
                "fecha_liberacion": ahora,
                "actualizado_en": ahora,
                "liberado_por": usuario_id,
                "liberado_por_nombre": usuario_actual.get("nombre") or usuario_actual.get("email"),
            }
        },
    )

    espacio_actualizado = None
    espacio_object_id = object_id_or_none(espacio_id)

    if espacio_object_id:
        await coleccion_espacios.update_one(
            {"_id": espacio_object_id},
            {
                "$set": {
                    "estado_actual": "disponible",
                    "actualizado_en": ahora,
                }
            },
        )

        espacio_actualizado = await coleccion_espacios.find_one(
            {"_id": espacio_object_id}
        )

    reserva_actualizada = await coleccion_reservas.find_one(
        {"_id": reserva["_id"]}
    )

    await emitir_eventos_reservas("liberar_clase_actual")

    return {
        "message": "Aula liberada correctamente.",
        "reserva": await convertir_reserva_completa(reserva_actualizada),
        "espacio": convertir_espacio(espacio_actualizado),
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
    rol = obtener_rol(usuario_actual)
    ahora = obtener_hora_ecuador()

    reserva_object_id = obtener_object_id(reserva_id)

    filtro = {
        "_id": reserva_object_id,
        **filtro_reservas_vigentes(),
    }

    if rol != "admin":
        filtro["usuario_id"] = usuario_id

    reserva = await coleccion_reservas.find_one(filtro)

    if not reserva:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró la reserva vigente o no tienes permisos para liberarla.",
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
                "fecha_liberacion": ahora,
                "actualizado_en": ahora,
                "liberado_por": usuario_id,
                "liberado_por_nombre": usuario_actual.get("nombre") or usuario_actual.get("email"),
            }
        },
    )

    espacio_actualizado = None
    espacio_object_id = object_id_or_none(espacio_id)

    if espacio_object_id:
        await coleccion_espacios.update_one(
            {"_id": espacio_object_id},
            {
                "$set": {
                    "estado_actual": "disponible",
                    "actualizado_en": ahora,
                }
            },
        )

        espacio_actualizado = await coleccion_espacios.find_one(
            {"_id": espacio_object_id}
        )

    reserva_actualizada = await coleccion_reservas.find_one(
        {"_id": reserva["_id"]}
    )

    await emitir_eventos_reservas("liberar_reserva")

    return {
        "message": "Reserva liberada correctamente.",
        "reserva": await convertir_reserva_completa(reserva_actualizada),
        "espacio": convertir_espacio(espacio_actualizado),
    }


@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva reserva",
)
async def crear_reserva(
    reserva: ReservaCreate,
    usuario_actual: dict = Depends(requerir_roles("Docente", "Admin")),
):
    id_espacio_objeto = obtener_object_id(reserva.espacio_id)

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
    nueva_reserva["docente_email"] = usuario_actual.get("email")
    nueva_reserva["email"] = usuario_actual.get("email")
    nueva_reserva["espacio_nombre"] = espacio_existe.get("nombre")
    nueva_reserva["espacio_bloque"] = espacio_existe.get("bloque")
    nueva_reserva["ubicacion"] = (
        espacio_existe.get("ubicacion")
        or espacio_existe.get("referencia")
        or espacio_existe.get("direccion")
        or espacio_existe.get("bloque")
        or "Ubicación no registrada"
    )
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

    await emitir_eventos_reservas("crear_reserva")

    return await convertir_reserva_completa(reserva_guardada)


@router.get(
    "/",
    response_model=List[dict],
    summary="Listar todas las reservas",
)
async def listar_reservas(
    usuario_actual: dict = Depends(requerir_roles("Admin")),
):
    reservas = []
    cursor = coleccion_reservas.find().sort("hora_inicio", 1)

    async for documento in cursor:
        reservas.append(await convertir_reserva_completa(documento))

    return reservas