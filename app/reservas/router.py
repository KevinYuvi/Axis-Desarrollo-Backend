from fastapi import APIRouter, HTTPException, status
from typing import List
from app.reservas.schemas import ReservaCreate, ReservaResponse
from app.database import db
from bson import ObjectId
from bson.errors import InvalidId

router = APIRouter(prefix="/reservas", tags=["Reservas"])

coleccion_reservas = db["reservas"]
coleccion_espacios = db["espacios"]

@router.post("/", response_model=ReservaResponse, status_code=status.HTTP_201_CREATED)
async def crear_reserva(reserva: ReservaCreate):
    # 1. Validar formato del espacio_id
    try:
        id_espacio_objeto = ObjectId(reserva.espacio_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id del espacio enviado no tiene un formato válido de MongoDB"
        )
    
    # 2. Verificar si el espacio existe
    espacio_existe = await coleccion_espacios.find_one({"_id": id_espacio_objeto})
    if not espacio_existe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El espacio con ID '{reserva.espacio_id}' no existe"
        )
        
    # 3. ALGORITMO: Validar que no haya choque de horarios para ese mismo espacio
    # Las fechas provienen de Pydantic como objetos datetime de Python
    reserva_en_conflicto = await coleccion_reservas.find_one({
        "espacio_id": reserva.espacio_id,
        "hora_inicio": {"$lt": reserva.hora_fin},
        "hora_fin": {"$gt": reserva.hora_inicio}
    })
    
    if reserva_en_conflicto:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El espacio no está disponible en el horario seleccionado. Ya existe una reserva activa."
        )
    
    # 4. Si pasa los filtros, se guarda
    nueva_reserva = reserva.model_dump()
    resultado = await coleccion_reservas.insert_one(nueva_reserva)
    
    reserva_guardada = await coleccion_reservas.find_one({"_id": resultado.inserted_id})
    if not reserva_guardada:
        raise HTTPException(status_code=500, detail="Error al guardar la reserva")
        
    reserva_guardada["id"] = str(reserva_guardada["_id"])
    return reserva_guardada

@router.get("/", response_model=List[ReservaResponse])
async def listar_reservas():
    reservas = []
    cursor = coleccion_reservas.find()
    async for documento in cursor:
        documento["id"] = str(documento["_id"])
        reservas.append(documento)
    return reservas