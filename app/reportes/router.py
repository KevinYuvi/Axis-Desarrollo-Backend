from fastapi import APIRouter, HTTPException, status
from typing import List
from app.reportes.schemas import ReporteCreate, ReporteResponse
from app.database import db

router = APIRouter(prefix="/reportes", tags=["Reportes"])

coleccion_reportes = db["reportes"]

@router.post("/", response_model=ReporteResponse, status_code=status.HTTP_201_CREATED)
async def crear_reporte(reporte: ReporteCreate):
    nuevo_reporte = reporte.model_dump()
    
    # Pydantic genera la fecha por defecto si viene vacía, Mongo la almacena
    resultado = await coleccion_reportes.insert_one(nuevo_reporte)
    reporte_guardado = await coleccion_reportes.find_one({"_id": resultado.inserted_id})
    
    if not reporte_guardado:
        raise HTTPException(status_code=500, detail="Error al registrar el reporte")
        
    reporte_guardado["id"] = str(reporte_guardado["_id"])
    return reporte_guardado

@router.get("/", response_model=List[ReporteResponse])
async def listar_reportes():
    reportes = []
    cursor = coleccion_reportes.find()
    async for documento in cursor:
        documento["id"] = str(documento["_id"])
        reportes.append(documento)
    return reportes