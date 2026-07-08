from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from bson import ObjectId
from bson.errors import InvalidId

from app.reportes.schemas import ReporteCreate, ReporteResponse
from app.database import db
from app.usuarios.utils import verificar_roles


router = APIRouter(prefix="/reportes", tags=["Reportes"])

# Colección donde se guardan los reportes/incidencias
coleccion_reportes = db["reportes"]

# Colección de espacios para validar que el aula/espacio exista
coleccion_espacios = db["espacios"]


@router.post("/", response_model=ReporteResponse, status_code=status.HTTP_201_CREATED)
async def crear_reporte(
    reporte: ReporteCreate,

    # Solo Ayudante y Admin pueden crear reportes
    usuario: dict = Depends(verificar_roles("Ayudante", "Admin"))
):
    # 1. Validar que el espacio_id tenga formato válido de MongoDB
    try:
        id_espacio_objeto = ObjectId(reporte.espacio_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id del espacio enviado no tiene un formato válido de MongoDB"
        )

    # 2. Verificar que el espacio exista en la colección espacios
    espacio_existe = await coleccion_espacios.find_one(
        {"_id": id_espacio_objeto}
    )

    if not espacio_existe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El espacio con ID '{reporte.espacio_id}' no existe"
        )

    # 3. Convertir el reporte recibido a diccionario
    nuevo_reporte = reporte.model_dump()

    # 4. Guardar quién creó el reporte usando el usuario del token JWT
    nuevo_reporte["creado_por"] = usuario["email"]
    nuevo_reporte["nombre_creador"] = usuario["nombre"]
    nuevo_reporte["rol_creador"] = usuario["rol"]

    # 5. Guardar el reporte en MongoDB
    resultado = await coleccion_reportes.insert_one(nuevo_reporte)

    # 6. Recuperar el reporte guardado
    reporte_guardado = await coleccion_reportes.find_one(
        {"_id": resultado.inserted_id}
    )

    if not reporte_guardado:
        raise HTTPException(
            status_code=500,
            detail="Error al registrar el reporte"
        )

    # 7. Convertir _id de MongoDB a id para la respuesta
    reporte_guardado["id"] = str(reporte_guardado["_id"])

    return reporte_guardado


@router.get("/", response_model=List[ReporteResponse])
async def listar_reportes(
    # Solo Admin puede listar todos los reportes
    usuario: dict = Depends(verificar_roles("Admin"))
):
    reportes = []

    # Consultar todos los reportes existentes
    cursor = coleccion_reportes.find()

    # Recorrer los documentos de MongoDB
    async for documento in cursor:
        documento["id"] = str(documento["_id"])
        reportes.append(documento)

    return reportes