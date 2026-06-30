from fastapi import APIRouter, HTTPException, status
from typing import List
from app.reservas.schemas import ReservaCreate, ReservaResponse
from app.database import db

router = APIRouter(prefix="/reservas", tags=["Reservas"])

# Colección específica en Mongo
coleccion_reservas = db["reservas"]

@router.post("/", response_model=ReservaResponse, status_code=status.HTTP_201_CREATED)
async def crear_reserva(reserva: ReservaCreate):
    nueva_reserva = reserva.model_dump()
    
    # IMPORTANTE: Aquí Mongo guardará las fechas nativas de Python (datetime) automáticamente
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