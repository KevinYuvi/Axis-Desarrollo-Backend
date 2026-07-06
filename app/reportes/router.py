from fastapi import APIRouter, HTTPException, status
from typing import List
from app.reportes.schemas import ReporteCreate, ReporteResponse
from app.database import db
from bson import ObjectId
from bson.errors import InvalidId

router = APIRouter(prefix="/reportes", tags=["Reportes"])

coleccion_reportes = db["reportes"]
coleccion_espacios = db["espacios"]

@router.post("/", response_model=ReporteResponse, status_code=status.HTTP_201_CREATED)
async def crear_reporte(reporte: ReporteCreate):
    # 1. Validar formato de MongoDB del espacio_id recibido
    try:
        id_espacio_objeto = ObjectId(reporte.espacio_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id del espacio enviado no tiene un formato válido de MongoDB"
        )
    
    # 2. Verificar si el espacio existe físicamente en la BD
    espacio_existe = await coleccion_espacios.find_one({"_id": id_espacio_objeto})
    
    if not espacio_existe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El espacio con ID '{reporte.espacio_id}' no existe"
        )
    
    # 3. Si todo está correcto, guardar el reporte de la incidencia
    nuevo_reporte = reporte.model_dump()
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
        
        if "_id" in documento:
            del documento["_id"]
            
        # 🔥 SOLUCIÓN AL ERROR: Si espacio_id es None o no existe, garantizamos que sea un string
        if documento.get("espacio_id") is None:
            # Si tiene el campo 'aula' de esquemas antiguos, lo usamos; si no, string vacío
            documento["espacio_id"] = documento.get("aula") or ""
            
        if "gravedad" not in documento:
            documento["gravedad"] = documento.get("prioridad", "baja").lower()
            
        if "fecha_reporte" not in documento:
            fecha = documento.get("fecha_creacion")
            documento["fecha_reporte"] = fecha.isoformat() if hasattr(fecha, "isoformat") else str(fecha) if fecha else datetime.utcnow().isoformat()
            
        if "estado" not in documento:
            documento["estado"] = "abierto"

        reportes.append(documento)
        
    return reportes