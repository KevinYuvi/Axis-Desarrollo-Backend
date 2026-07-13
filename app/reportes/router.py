from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from datetime import datetime, timedelta

from app.reportes.schemas import ReporteCreate, ReporteResponse
from app.database import db
from app.usuarios.utils import requerir_roles

from bson import ObjectId
from bson.errors import InvalidId

from app.realtime.manager import realtime_manager

router = APIRouter(prefix="/reportes", tags=["Reportes"])

coleccion_reportes = db["reportes"]
coleccion_espacios = db["espacios"]


def obtener_hora_ecuador() -> datetime:
    return datetime.utcnow() - timedelta(hours=5)


def obtener_object_id(id_valor: str) -> ObjectId:
    try:
        return ObjectId(id_valor)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id enviado no tiene un formato válido de MongoDB",
        )


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


def convertir_reporte(documento: dict) -> dict:
    documento["id"] = str(documento["_id"])
    documento.pop("_id", None)

    documento.setdefault("recurso_afectado", "General")
    documento.setdefault("codigo", None)

    return documento


@router.post(
    "/",
    response_model=ReporteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear reporte de incidencia",
)
async def crear_reporte(
    reporte: ReporteCreate,
    usuario_actual: dict = Depends(requerir_roles("Docente", "Ayudante", "Admin")),
    ):
    espacio_object_id = obtener_object_id(reporte.espacio_id)

    espacio_existe = await coleccion_espacios.find_one(
        {"_id": espacio_object_id}
    )

    if not espacio_existe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El espacio con ID '{reporte.espacio_id}' no existe",
        )

    usuario_id = obtener_usuario_id(usuario_actual)

    nuevo_reporte = reporte.model_dump()

    nuevo_reporte["usuario_id"] = usuario_id
    nuevo_reporte["docente_nombre"] = usuario_actual.get("nombre", "Docente AXIS")
    nuevo_reporte["espacio_nombre"] = espacio_existe.get(
        "nombre",
        "Espacio académico",
    )
    nuevo_reporte["espacio_bloque"] = espacio_existe.get("bloque")
    nuevo_reporte["fecha_reporte"] = obtener_hora_ecuador()
    nuevo_reporte["estado"] = "abierto"

    total_usuario = await coleccion_reportes.count_documents(
        {"usuario_id": usuario_id}
    )

    nuevo_reporte["codigo"] = f"TK-{total_usuario + 1:03d}"

    resultado = await coleccion_reportes.insert_one(nuevo_reporte)

    reporte_guardado = await coleccion_reportes.find_one(
        {"_id": resultado.inserted_id}
    )

    if not reporte_guardado:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al registrar el reporte",
        )

    await realtime_manager.emitir({
        "tipo": "reportes_actualizados",
        "origen": "crear_reporte",
    })

    await realtime_manager.emitir({
        "tipo": "dashboard_actualizado",
        "origen": "crear_reporte",
    })

    return convertir_reporte(reporte_guardado)


@router.get(
    "/mis-reportes",
    response_model=List[ReporteResponse],
    summary="Listar mis reportes",
)
async def listar_mis_reportes(
    usuario_actual: dict = Depends(requerir_roles("Docente", "Ayudante", "Admin")),
):
    usuario_id = obtener_usuario_id(usuario_actual)

    reportes = []

    cursor = coleccion_reportes.find(
        {"usuario_id": usuario_id}
    ).sort("fecha_reporte", -1)

    async for documento in cursor:
        reportes.append(convertir_reporte(documento))

    return reportes


@router.get(
    "/",
    response_model=List[ReporteResponse],
    summary="Listar todos los reportes",
)
async def listar_reportes(
    usuario_actual: dict = Depends(requerir_roles("Admin", "Ayudante")),
):
    reportes = []

    cursor = coleccion_reportes.find().sort("fecha_reporte", -1)

    async for documento in cursor:
        reportes.append(convertir_reporte(documento))

    return reportes


@router.patch(
    "/{reporte_id}/estado",
    response_model=ReporteResponse,
    summary="Actualizar estado de un reporte",
)
async def actualizar_estado_reporte(
    reporte_id: str,
    nuevo_estado: str,
    usuario_actual: dict = Depends(requerir_roles("Admin", "Ayudante")),
    ):
    estados_permitidos = ["abierto", "en_proceso", "resuelto"]

    if nuevo_estado not in estados_permitidos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado no permitido. Usa: abierto, en_proceso o resuelto",
        )

    reporte_object_id = obtener_object_id(reporte_id)

    reporte_existe = await coleccion_reportes.find_one(
        {"_id": reporte_object_id}
    )

    if not reporte_existe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El reporte con ID '{reporte_id}' no existe",
        )

    await coleccion_reportes.update_one(
        {"_id": reporte_object_id},
        {
            "$set": {
                "estado": nuevo_estado,
                "fecha_actualizacion": obtener_hora_ecuador(),
            }
        },
    )

    reporte_actualizado = await coleccion_reportes.find_one(
        {"_id": reporte_object_id}
    )

    await realtime_manager.emitir({
        "tipo": "reportes_actualizados",
        "origen": "actualizar_estado_reporte",
    })

    await realtime_manager.emitir({
        "tipo": "dashboard_actualizado",
        "origen": "actualizar_estado_reporte",
    })

    return convertir_reporte(reporte_actualizado)