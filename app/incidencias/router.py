# Importamos herramientas principales de FastAPI
from fastapi import APIRouter, HTTPException, status, Depends

# ObjectId permite trabajar con los IDs propios de MongoDB
from bson import ObjectId

# datetime y timezone permiten guardar fecha y hora exacta en UTC
from datetime import datetime, timezone

# Importamos la conexión a la base de datos MongoDB
from app.database import db

# Importamos los modelos de datos definidos en schemas.py
from app.incidencias.schemas import (
    IncidenciaCreate,
    IncidenciaResponse,
    IncidenciaEstadoUpdate,
    EstadoIncidenciaEnum
)

# Importamos funciones de seguridad y validación de roles
from app.usuarios.utils import verificar_roles


# Creamos el router de incidencias
# prefix="/incidencias" significa que todas las rutas empezarán con /incidencias
# tags=["Incidencias"] agrupa estas rutas en Swagger
router = APIRouter(prefix="/incidencias", tags=["Incidencias"])


# Seleccionamos la colección "incidencias" dentro de MongoDB
coleccion_incidencias = db["incidencias"]


# Función auxiliar para convertir el _id de MongoDB a id tipo texto
def convertir_incidencia(incidencia) -> dict:
    # MongoDB usa "_id", pero el frontend espera "id"
    incidencia["id"] = str(incidencia["_id"])

    # Retornamos la incidencia transformada
    return incidencia


# Endpoint para crear una incidencia
# POST /incidencias/
@router.post(
    "/",
    response_model=IncidenciaResponse,
    status_code=status.HTTP_201_CREATED
)
async def crear_incidencia(
    # Datos que vienen desde el frontend o Swagger
    incidencia: IncidenciaCreate,

    # Solo usuarios con rol Ayudante o Admin pueden crear incidencias
    usuario: dict = Depends(verificar_roles("Ayudante", "Admin"))
):
    # Convertimos el modelo Pydantic a diccionario
    nueva_incidencia = incidencia.model_dump()

    # Toda incidencia nueva inicia como Pendiente
    nueva_incidencia["estado"] = EstadoIncidenciaEnum.PENDIENTE.value

    # Guardamos el correo del usuario que creó la incidencia
    nueva_incidencia["creado_por"] = usuario["email"]

    # Guardamos el nombre del usuario que creó la incidencia
    nueva_incidencia["nombre_creador"] = usuario["nombre"]

    # Guardamos la fecha y hora actual
    nueva_incidencia["fecha_creacion"] = datetime.now(timezone.utc)

    # Insertamos la incidencia en MongoDB
    resultado = await coleccion_incidencias.insert_one(nueva_incidencia)

    # Buscamos la incidencia recién guardada usando su ID
    incidencia_guardada = await coleccion_incidencias.find_one(
        {"_id": resultado.inserted_id}
    )

    # Convertimos el _id de Mongo a id y retornamos la respuesta
    return convertir_incidencia(incidencia_guardada)


# Endpoint para listar todas las incidencias
# GET /incidencias/
@router.get("/", response_model=list[IncidenciaResponse])
async def listar_incidencias(
    # Solo el Admin puede ver todas las incidencias
    usuario: dict = Depends(verificar_roles("Admin"))
):
    # Creamos una lista vacía donde se guardarán las incidencias
    incidencias = []

    # Consultamos todas las incidencias de MongoDB
    cursor = coleccion_incidencias.find()

    # Recorremos cada incidencia encontrada
    async for incidencia in cursor:
        # Convertimos _id a id y la agregamos a la lista
        incidencias.append(convertir_incidencia(incidencia))

    # Retornamos todas las incidencias
    return incidencias


# Endpoint para listar las incidencias creadas por el usuario actual
# GET /incidencias/mis-incidencias
@router.get("/mis-incidencias", response_model=list[IncidenciaResponse])
async def listar_mis_incidencias(
    # Ayudante y Admin pueden ver sus propias incidencias
    usuario: dict = Depends(verificar_roles("Ayudante", "Admin"))
):
    # Lista vacía para guardar resultados
    incidencias = []

    # Buscamos solo incidencias creadas por el correo del usuario actual
    cursor = coleccion_incidencias.find(
        {"creado_por": usuario["email"]}
    )

    # Recorremos las incidencias encontradas
    async for incidencia in cursor:
        # Convertimos _id a id y agregamos a la lista
        incidencias.append(convertir_incidencia(incidencia))

    # Retornamos las incidencias del usuario actual
    return incidencias


# Endpoint para actualizar el estado de una incidencia
# PUT /incidencias/{incidencia_id}/estado
@router.put("/{incidencia_id}/estado", response_model=IncidenciaResponse)
async def actualizar_estado_incidencia(
    # ID de la incidencia enviado en la URL
    incidencia_id: str,

    # Datos del nuevo estado enviados en el body
    datos: IncidenciaEstadoUpdate,

    # Solo Admin puede cambiar el estado de una incidencia
    usuario: dict = Depends(verificar_roles("Admin"))
):
    # Verificamos que el ID tenga formato válido de MongoDB
    if not ObjectId.is_valid(incidencia_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de incidencia inválido"
        )

    # Actualizamos el estado de la incidencia en MongoDB
    resultado = await coleccion_incidencias.update_one(
        {"_id": ObjectId(incidencia_id)},
        {"$set": {"estado": datos.estado.value}}
    )

    # Si no se encontró ninguna incidencia con ese ID
    if resultado.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incidencia no encontrada"
        )

    # Buscamos la incidencia actualizada
    incidencia_actualizada = await coleccion_incidencias.find_one(
        {"_id": ObjectId(incidencia_id)}
    )

    # Convertimos _id a id y retornamos la incidencia actualizada
    return convertir_incidencia(incidencia_actualizada)