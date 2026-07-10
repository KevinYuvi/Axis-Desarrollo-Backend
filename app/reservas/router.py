from datetime import datetime, time, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from bson.errors import InvalidId

from app.reservas.schemas import ReservaCreate, ReservaResponse, MiClaseActualResponse
from app.database import db
from app.usuarios.utils import obtener_usuario_actual, requerir_roles


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
            detail="El id del espacio enviado no tiene un formato válido de MongoDB",
        )


def convertir_reserva(documento: dict) -> dict:
    documento["id"] = str(documento["_id"])
    documento.pop("_id", None)
    # Reservas antiguas no tienen campos de check-in: se completan con valores por defecto
    documento.setdefault("checkin", False)
    documento.setdefault("checkin_hora", None)
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
        or usuario_actual.get("user_id")
    )

    if not usuario_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo determinar el ID del usuario desde el token",
        )

    return str(usuario_id)


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

    print("DOCENTE AUTENTICADO:", usuario_id)
    print("HORA ACTUAL ECUADOR:", ahora)

    reserva = await coleccion_reservas.find_one(
        {
            "usuario_id": usuario_id,
            "hora_inicio": {"$lte": ahora},
            "hora_fin": {"$gte": ahora},
        }
    )

    print("RESERVA ACTIVA ENCONTRADA:", reserva)

    if not reserva and usuario_id == "mock-docente-id":
        reserva = {
            "_id": ObjectId("649c55b9f1234567890fbcde"),
            "espacio_id": "649c12a3f1234567890abcde",
            "materia": "Programación Móvil (Clase Activa)",
            "hora_inicio": ahora - timedelta(minutes=30),
            "hora_fin": ahora + timedelta(minutes=90),
            "usuario_id": "mock-docente-id",
            "docente_nombre": "Profesor de Prueba",
            "checkin": False,
            "checkin_hora": None
        }

    if not reserva:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró una clase activa para el docente autenticado",
        )

    espacio = None
    espacio_id_str = str(reserva.get("espacio_id"))
    if espacio_id_str == "649c12a3f1234567890abcde":
        espacio = {
            "_id": ObjectId("649c12a3f1234567890abcde"),
            "nombre": "Aula FICA 101",
            "tipo": "Aula",
            "capacidad": 40,
            "estado_actual": "disponible",
            "coordenadas_gps": "-0.1995,-78.5042"
        }
    elif espacio_id_str == "649c12a3f1234567890abcd0":
        espacio = {
            "_id": ObjectId("649c12a3f1234567890abcd0"),
            "nombre": "Aula FICA 102",
            "tipo": "Aula",
            "capacidad": 35,
            "estado_actual": "disponible",
            "coordenadas_gps": "-0.2012,-78.5001"
        }
    else:
        try:
            espacio_object_id = obtener_object_id(reserva["espacio_id"])
            espacio = await coleccion_espacios.find_one({"_id": espacio_object_id})
        except HTTPException:
            pass

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

    print("DOCENTE AUTENTICADO:", usuario_id)
    print("INICIO DÍA ECUADOR:", inicio_dia)
    print("FIN DÍA ECUADOR:", fin_dia)

    cursor = coleccion_reservas.find(
        {
            "usuario_id": usuario_id,
            "hora_inicio": {"$lt": fin_dia},
            "hora_fin": {"$gt": inicio_dia},
        }
    ).sort("hora_inicio", 1)

    cronograma_hoy = []

    async for reserva in cursor:
        cronograma_hoy.append(reserva)
    if usuario_id == "mock-docente-id":
        mock_reservas = [
            {
                "_id": ObjectId("649c55b9f1234567890fbcde"),
                "espacio_id": "649c12a3f1234567890abcde",
                "materia": "Programación Móvil (Clase Activa)",
                "hora_inicio": ahora - timedelta(minutes=30),
                "hora_fin": ahora + timedelta(minutes=90),
                "usuario_id": "mock-docente-id",
                "docente_nombre": "Profesor de Prueba",
                "checkin": False,
                "checkin_hora": None
            },
            {
                "_id": ObjectId("649c55b9f1234567890fbcdf"),
                "espacio_id": "649c12a3f1234567890abcd0",
                "materia": "Sistemas Operativos (Siguiente Clase)",
                "hora_inicio": ahora + timedelta(hours=2),
                "hora_fin": ahora + timedelta(hours=4),
                "usuario_id": "mock-docente-id",
                "docente_nombre": "Profesor de Prueba",
                "checkin": False,
                "checkin_hora": None
            }
        ]
        ids_existentes = {str(r["_id"]) for r in cronograma_hoy}
        for mr in mock_reservas:
            if str(mr["_id"]) not in ids_existentes:
                cronograma_hoy.append(mr)

    respuesta = []
    for r in cronograma_hoy:
        espacio = None
        espacio_id_str = str(r.get("espacio_id"))
        if espacio_id_str == "649c12a3f1234567890abcde":
            espacio = {
                "_id": ObjectId("649c12a3f1234567890abcde"),
                "nombre": "Aula FICA 101",
                "tipo": "Aula",
                "capacidad": 40,
                "estado_actual": "disponible",
                "coordenadas_gps": "-0.1995,-78.5042"
            }
        elif espacio_id_str == "649c12a3f1234567890abcd0":
            espacio = {
                "_id": ObjectId("649c12a3f1234567890abcd0"),
                "nombre": "Aula FICA 102",
                "tipo": "Aula",
                "capacidad": 35,
                "estado_actual": "disponible",
                "coordenadas_gps": "-0.2012,-78.5001"
            }
        else:
            try:
                espacio_object_id = obtener_object_id(r["espacio_id"])
                espacio = await coleccion_espacios.find_one({"_id": espacio_object_id})
            except HTTPException:
                pass

        respuesta.append({
            "reserva": convertir_reserva(r),
            "espacio": convertir_espacio(espacio) if espacio else None,
        })

    return respuesta


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
    espacio_existe = None
    if reserva.espacio_id == "649c12a3f1234567890abcde":
        espacio_existe = {"_id": ObjectId("649c12a3f1234567890abcde")}
    elif reserva.espacio_id == "649c12a3f1234567890abcd0":
        espacio_existe = {"_id": ObjectId("649c12a3f1234567890abcd0")}
    else:
        try:
            id_espacio_objeto = ObjectId(reserva.espacio_id)
            espacio_existe = await coleccion_espacios.find_one({"_id": id_espacio_objeto})
        except InvalidId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El id del espacio enviado no tiene un formato válido de MongoDB",
            )

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

    usuario_id = obtener_usuario_id(usuario_actual)

    nueva_reserva = reserva.model_dump()
    nueva_reserva["usuario_id"] = usuario_id
    nueva_reserva["docente_nombre"] = usuario_actual.get("nombre", "Docente AXIS")

    resultado = await coleccion_reservas.insert_one(nueva_reserva)

    reserva_guardada = await coleccion_reservas.find_one(
        {"_id": resultado.inserted_id}
    )

    if not reserva_guardada:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar la reserva",
        )

    return convertir_reserva(reserva_guardada)


@router.patch(
    "/{reserva_id}/checkin",
    summary="Check-in de clase (Ayudante/Docente)",
)
async def checkin_reserva(
    reserva_id: str,
    usuario_actual: dict = Depends(requerir_roles("Docente", "Ayudante", "Admin")),
):
    """
    Confirma que el grupo está presente en el aula para que la reserva
    no se libere por inasistencia (Planteamiento §C).
    """
    reserva_object_id = obtener_object_id(reserva_id)

    ahora = obtener_hora_ecuador()

    resultado = await coleccion_reservas.update_one(
        {"_id": reserva_object_id},
        {
            "$set": {
                "checkin": True,
                "checkin_hora": ahora,
                "checkin_por": obtener_usuario_id(usuario_actual),
            }
        },
    )

    if resultado.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva no encontrada",
        )

    return {"mensaje": "Check-in registrado", "reserva_id": reserva_id}


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