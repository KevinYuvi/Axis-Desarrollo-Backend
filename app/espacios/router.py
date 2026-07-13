from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, HTTPException, status, Depends
from bson import ObjectId
from bson.errors import InvalidId

from app.espacios.schemas import EspacioCreate, EspacioResponse
from app.database import db
from app.usuarios.utils import requerir_roles

from app.realtime.manager import realtime_manager

router = APIRouter(prefix="/espacios", tags=["Espacios"])

coleccion_espacios = db["espacios"]


ESTADOS_VALIDOS = ["disponible", "ocupado", "mantenimiento"]


def obtener_hora_ecuador() -> datetime:
    return datetime.utcnow() - timedelta(hours=5)


def convertir_espacio(documento: dict) -> dict:
    documento["id"] = str(documento["_id"])
    documento.pop("_id", None)
    return documento


def obtener_object_id(id_valor: str) -> ObjectId:
    try:
        return ObjectId(id_valor)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id del espacio enviado no tiene un formato válido de MongoDB",
        )


@router.post(
    "/",
    response_model=EspacioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear espacio académico",
)
async def crear_espacio(
    espacio: EspacioCreate,
    usuario_actual: dict = Depends(requerir_roles("Admin")),
):
    ahora = obtener_hora_ecuador()

    nuevo_espacio = espacio.model_dump()

    if not nuevo_espacio.get("estado_actual"):
        nuevo_espacio["estado_actual"] = "disponible"

    if nuevo_espacio["estado_actual"] not in ESTADOS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El estado del espacio no es válido",
        )

    nuevo_espacio["creado_en"] = ahora
    nuevo_espacio["actualizado_en"] = ahora

    resultado = await coleccion_espacios.insert_one(nuevo_espacio)

    espacio_guardado = await coleccion_espacios.find_one(
        {"_id": resultado.inserted_id}
    )

    if not espacio_guardado:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar el espacio en la base de datos",
        )
    
    await realtime_manager.emitir({
        "tipo": "aulas_actualizadas",
        "origen": "crear_espacio",
    })

    await realtime_manager.emitir({
        "tipo": "dashboard_actualizado",
        "origen": "crear_espacio",
    })

    return convertir_espacio(espacio_guardado)


@router.get(
    "/",
    response_model=List[EspacioResponse],
    summary="Listar espacios académicos",
)
async def listar_espacios(
    usuario_actual: dict = Depends(
        requerir_roles("Estudiante", "Docente", "Admin")
    ),
):
    espacios = []
    cursor = coleccion_espacios.find().sort("nombre", 1)

    async for documento in cursor:
        espacios.append(convertir_espacio(documento))

    return espacios


@router.get(
    "/estado-actual",
    response_model=List[EspacioResponse],
    summary="Consultar estado actual de espacios",
)
async def obtener_estado_actual(
    usuario_actual: dict = Depends(
        requerir_roles("Estudiante", "Docente", "Admin")
    ),
):
    espacios = []
    cursor = coleccion_espacios.find().sort("nombre", 1)

    async for documento in cursor:
        espacios.append(convertir_espacio(documento))

    return espacios


@router.get(
    "/{espacio_id}",
    response_model=EspacioResponse,
    summary="Consultar detalle de un espacio",
)
async def obtener_detalle_espacio(
    espacio_id: str,
    usuario_actual: dict = Depends(
        requerir_roles("Estudiante", "Docente", "Admin")
    ),
):
    espacio_object_id = obtener_object_id(espacio_id)

    espacio = await coleccion_espacios.find_one({"_id": espacio_object_id})

    if not espacio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El espacio con ID '{espacio_id}' no existe",
        )

    return convertir_espacio(espacio)


@router.patch(
    "/{espacio_id}",
    response_model=EspacioResponse,
    summary="Actualizar datos de un espacio académico",
)
async def actualizar_espacio(
    espacio_id: str,
    datos: dict,
    usuario_actual: dict = Depends(requerir_roles("Admin")),
    ):
    espacio_object_id = obtener_object_id(espacio_id)

    espacio_existe = await coleccion_espacios.find_one({"_id": espacio_object_id})

    if not espacio_existe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El espacio con ID '{espacio_id}' no existe",
        )

    campos_permitidos = {
        "nombre",
        "ubicacion",
        "bloque",
        "capacidad",
        "tipo",
        "equipamiento",
        "estado_actual",
    }

    datos_limpios = {}

    for campo, valor in datos.items():
        if campo in campos_permitidos:
            datos_limpios[campo] = valor

    if not datos_limpios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se enviaron campos válidos para actualizar",
        )

    if "estado_actual" in datos_limpios:
        if datos_limpios["estado_actual"] not in ESTADOS_VALIDOS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El estado del espacio no es válido",
            )

    if "capacidad" in datos_limpios:
        try:
            datos_limpios["capacidad"] = int(datos_limpios["capacidad"])
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La capacidad debe ser un número válido",
            )

        if datos_limpios["capacidad"] < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La capacidad no puede ser negativa",
            )

    if "equipamiento" in datos_limpios:
        if not isinstance(datos_limpios["equipamiento"], list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El equipamiento debe enviarse como una lista",
            )

    datos_limpios["actualizado_en"] = obtener_hora_ecuador()

    await coleccion_espacios.update_one(
        {"_id": espacio_object_id},
        {"$set": datos_limpios},
    )

    espacio_actualizado = await coleccion_espacios.find_one(
        {"_id": espacio_object_id}
    )

    if not espacio_actualizado:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar el espacio",
        )

    await realtime_manager.emitir({
        "tipo": "aulas_actualizadas",
        "origen": "actualizar_espacio",
    })

    await realtime_manager.emitir({
        "tipo": "dashboard_actualizado",
        "origen": "actualizar_espacio",
    })

    return convertir_espacio(espacio_actualizado)


@router.patch(
    "/{espacio_id}/estado",
    response_model=EspacioResponse,
    summary="Cambiar estado de un espacio académico",
)
async def cambiar_estado_espacio(
    espacio_id: str,
    nuevo_estado: str,
    usuario_actual: dict = Depends(requerir_roles("Admin")),
    ):
    if nuevo_estado not in ESTADOS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El estado enviado no es válido",
        )

    espacio_object_id = obtener_object_id(espacio_id)

    espacio_existe = await coleccion_espacios.find_one({"_id": espacio_object_id})

    if not espacio_existe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El espacio con ID '{espacio_id}' no existe",
        )

    await coleccion_espacios.update_one(
        {"_id": espacio_object_id},
        {
            "$set": {
                "estado_actual": nuevo_estado,
                "actualizado_en": obtener_hora_ecuador(),
            }
        },
    )

    espacio_actualizado = await coleccion_espacios.find_one(
        {"_id": espacio_object_id}
    )

    if not espacio_actualizado:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al cambiar el estado del espacio",
        )

    await realtime_manager.emitir({
        "tipo": "aulas_actualizadas",
        "origen": "cambiar_estado_espacio",
    })

    await realtime_manager.emitir({
        "tipo": "dashboard_actualizado",
        "origen": "cambiar_estado_espacio",
    })

    return convertir_espacio(espacio_actualizado)


@router.patch(
    "/{espacio_id}/liberar",
    response_model=EspacioResponse,
    summary="Liberar un espacio académico",
)
async def liberar_espacio(
    espacio_id: str,
    usuario_actual: dict = Depends(requerir_roles("Docente", "Admin")),
    ):
    espacio_object_id = obtener_object_id(espacio_id)

    espacio_existe = await coleccion_espacios.find_one({"_id": espacio_object_id})

    if not espacio_existe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El espacio con ID '{espacio_id}' no existe",
        )

    await coleccion_espacios.update_one(
        {"_id": espacio_object_id},
        {
            "$set": {
                "estado_actual": "disponible",
                "actualizado_en": obtener_hora_ecuador(),
            }
        },
    )

    espacio_actualizado = await coleccion_espacios.find_one(
        {"_id": espacio_object_id}
    )

    if not espacio_actualizado:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al liberar el espacio",
        )

    await realtime_manager.emitir({
        "tipo": "aulas_actualizadas",
        "origen": "liberar_espacio",
    })

    await realtime_manager.emitir({
        "tipo": "reservas_actualizadas",
        "origen": "liberar_espacio",
    })

    await realtime_manager.emitir({
        "tipo": "dashboard_actualizado",
        "origen": "liberar_espacio",
    })

    return convertir_espacio(espacio_actualizado)