from fastapi import APIRouter, HTTPException
from app.reportes.schemas import ReporteCreate, ReporteResponse
from typing import List

router = APIRouter(prefix="/reportes", tags=["Reportes / Incidencias"])

# Base de datos simulada
db_reportes = []

@router.post("/", response_model=ReporteResponse, status_code=201)
def crear_reporte(reporte: ReporteCreate):
    nuevo_id = f"649c66a1f1234567890e{len(db_reportes):03d}"
    
    reporte_dict = reporte.model_dump()
    reporte_dict["id"] = nuevo_id
    
    db_reportes.append(reporte_dict)
    return reporte_dict

@router.get("/", response_model=List[ReporteResponse])
def listar_reportes():
    return db_reportes
