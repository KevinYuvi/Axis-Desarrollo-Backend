# Importamos herramientas de FastAPI
from fastapi import APIRouter, HTTPException, status, Depends

# ObjectId permite trabajar con IDs de MongoDB
from bson import ObjectId

# Importamos la conexión a MongoDB
from app.database import db

# Importamos los modelos del módulo aulas
from app.aulas.schemas import AulaCreate, AulaResponse, AulaEstadoUpdate, EstadoAulaEnum

# Importamos la validación de roles
from app.usuarios.utils import verificar_roles


# Creamos el router del módulo aulas
router = APIRouter(prefix="/aulas", tags=["Aulas"])


# Seleccionamos la colección aulas en MongoDB
coleccion_aulas = db["aulas"]


# Función para convertir el _id de MongoDB a id en texto
def convertir_aula(aula) -> dict:
    aula["id"] = str(aula["_id"])
    return aula


# Crear aula
# Solo el Admin puede crear aulas
@router.post("/", response_model=AulaResponse, status_code=status.HTTP_201_CREATED)
async def crear_aula(
    aula: AulaCreate,
    usuario: dict = Depends(verificar_roles("Admin"))
):
    # Convertimos el modelo recibido a diccionario
    nueva_aula = aula.model_dump()

    # Si no se envía motivo de bloqueo, queda como None
    nueva_aula["motivo_bloqueo"] = None

    # Guardamos el aula en MongoDB
    resultado = await coleccion_aulas.insert_one(nueva_aula)

    # Buscamos el aula recién creada
    aula_guardada = await coleccion_aulas.find_one(
        {"_id": resultado.inserted_id}
    )

    # Retornamos el aula con el id convertido
    return convertir_aula(aula_guardada)


# Listar todas las aulas
# Admin y Ayudante pueden consultar aulas
@router.get("/", response_model=list[AulaResponse])
async def listar_aulas(
    usuario: dict = Depends(verificar_roles("Admin", "Ayudante"))
):
    aulas = []

    # Consultamos todas las aulas
    cursor = coleccion_aulas.find()

    # Recorremos los resultados
    async for aula in cursor:
        aulas.append(convertir_aula(aula))

    return aulas


# Consultar aula por ID
@router.get("/{aula_id}", response_model=AulaResponse)
async def obtener_aula(
    aula_id: str,
    usuario: dict = Depends(verificar_roles("Admin", "Ayudante"))
):
    # Validamos que el ID sea correcto
    if not ObjectId.is_valid(aula_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de aula inválido"
        )

    # Buscamos el aula en MongoDB
    aula = await coleccion_aulas.find_one(
        {"_id": ObjectId(aula_id)}
    )

    # Si no existe, devolvemos error
    if not aula:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aula no encontrada"
        )

    return convertir_aula(aula)


# Actualizar estado del aula
# Solo Admin puede bloquear, desbloquear o poner en mantenimiento
@router.put("/{aula_id}/estado", response_model=AulaResponse)
async def actualizar_estado_aula(
    aula_id: str,
    datos: AulaEstadoUpdate,
    usuario: dict = Depends(verificar_roles("Admin"))
):
    # Validamos ID
    if not ObjectId.is_valid(aula_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de aula inválido"
        )

    # Datos que se van a actualizar
    datos_actualizacion = {
        "estado": datos.estado.value,
        "motivo_bloqueo": datos.motivo_bloqueo
    }

    # Si el aula vuelve a estar disponible, limpiamos el motivo de bloqueo
    if datos.estado == EstadoAulaEnum.DISPONIBLE:
        datos_actualizacion["motivo_bloqueo"] = None

    # Actualizamos el aula
    resultado = await coleccion_aulas.update_one(
        {"_id": ObjectId(aula_id)},
        {"$set": datos_actualizacion}
    )

    # Si no encontró el aula
    if resultado.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aula no encontrada"
        )

    # Consultamos el aula actualizada
    aula_actualizada = await coleccion_aulas.find_one(
        {"_id": ObjectId(aula_id)}
    )

    return convertir_aula(aula_actualizada)


# Endpoint rápido para bloquear aula
@router.put("/{aula_id}/bloquear", response_model=AulaResponse)
async def bloquear_aula(
    aula_id: str,
    motivo: str,
    usuario: dict = Depends(verificar_roles("Admin"))
):
    # Validamos ID
    if not ObjectId.is_valid(aula_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de aula inválido"
        )

    # Cambiamos estado a Bloqueada
    resultado = await coleccion_aulas.update_one(
        {"_id": ObjectId(aula_id)},
        {
            "$set": {
                "estado": EstadoAulaEnum.BLOQUEADA.value,
                "motivo_bloqueo": motivo
            }
        }
    )

    if resultado.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aula no encontrada"
        )

    aula_actualizada = await coleccion_aulas.find_one(
        {"_id": ObjectId(aula_id)}
    )

    return convertir_aula(aula_actualizada)