from fastapi import APIRouter, HTTPException
from app.reservas.schemas import ReservaCreate, ReservaResponse
from typing import List

router = APIRouter(prefix="/reservas", tags=["Reservas"])

# Base de datos simulada
db_reservas = []

@router.post("/", response_model=ReservaResponse, status_code=201)
def crear_reserva(reserva: ReservaCreate):
    # En un sistema real, aquí verificarías si el espacio_id existe en la BD de Espacios
    nuevo_id = f"649c55b9f1234567890f{len(db_reservas):03d}"
    
    reserva_dict = reserva.model_dump()
    reserva_dict["id"] = nuevo_id
    
    db_reservas.append(reserva_dict)
    return reserva_dict

@router.get("/", response_model=List[ReservaResponse])
def listar_reservas():
    return db_reservas
