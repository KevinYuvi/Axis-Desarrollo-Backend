from fastapi import APIRouter, HTTPException
from app.espacios.schemas import EspacioCreate, EspacioResponse
from typing import List

# Creamos el router. Prefix añade '/espacios' a todas las rutas de este archivo
router = APIRouter(prefix="/espacios", tags=["Espacios"])

# Base de datos simulada en memoria
db_espacios = []

@router.post("/", response_model=EspacioResponse, status_code=201)
def crear_espacio(espacio: EspacioCreate):
    # Generamos un ID simulado para MongoDB
    nuevo_id = f"649c12a3f1234567890a{len(db_espacios):03d}"
    
    # Convertimos el esquema Pydantic a diccionario y añadimos el ID
    espacio_dict = espacio.model_dump()
    espacio_dict["id"] = nuevo_id
    
    # Guardamos en nuestra lista
    db_espacios.append(espacio_dict)
    return espacio_dict

@router.get("/", response_model=List[EspacioResponse])
def listar_espacios():
    return db_espacios
