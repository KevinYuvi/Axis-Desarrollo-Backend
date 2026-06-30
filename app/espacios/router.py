from fastapi import APIRouter, HTTPException, status
from typing import List
from app.espacios.schemas import EspacioCreate, EspacioResponse
# Importamos la instancia de la base de datos de AXIS
from app.database import db 

router = APIRouter(prefix="/espacios", tags=["Espacios"])

# Definimos la colección específica dentro de MongoDB
coleccion_espacios = db["espacios"]

@router.post("/", response_model=EspacioResponse, status_code=status.HTTP_201_CREATED)
async def crear_espacio(espacio: EspacioCreate):
    # 1. Convertimos el esquema Pydantic a un diccionario de Python
    nuevo_espacio = espacio.model_dump()
    
    # 2. Insertamos el documento de forma asíncrona en MongoDB
    resultado = await coleccion_espacios.insert_one(nuevo_espacio)
    
    # 3. Recuperamos el documento recién creado usando el id generado por Mongo
    espacio_guardado = await coleccion_espacios.find_one({"_id": resultado.inserted_id})
    
    if not espacio_guardado:
        raise HTTPException(status_code=500, detail="Error al guardar el espacio en la base de datos")
    
    # 4. Mapeamos el '_id' (ObjectId) a 'id' (str) para cumplir con el esquema de salida
    espacio_guardado["id"] = str(espacio_guardado["_id"])
    return espacio_guardado


@router.get("/", response_model=List[EspacioResponse])
async def listar_espacios():
    espacios = []
    
    # Buscamos todos los documentos de la colección
    cursor = coleccion_espacios.find()
    
    # Iteramos asíncronamente sobre el cursor de MongoDB
    async for documento in cursor:
        documento["id"] = str(documento["_id"])
        espacios.append(documento)
        
    return espacios