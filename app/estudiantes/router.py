from fastapi import APIRouter

from app.estudiantes.schemas import ClasesHoyResponse, ProximaClaseResponse
from app.estudiantes import service

router = APIRouter(prefix="/estudiantes", tags=["Estudiantes"])


@router.get("/mis-clases-hoy", response_model=ClasesHoyResponse)
async def obtener_mis_clases_hoy():
    clases = await service.get_mis_clases_hoy()

    return {
        "ok": True,
        "message": "Clases del día obtenidas correctamente",
        "data": clases,
    }


@router.get("/proxima-clase", response_model=ProximaClaseResponse)
async def obtener_proxima_clase():
    clase = await service.get_proxima_clase()

    return {
        "ok": True,
        "message": "Próxima clase obtenida correctamente",
        "data": clase,
    }