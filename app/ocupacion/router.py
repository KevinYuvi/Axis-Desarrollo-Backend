from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.ocupacion import service
from app.ocupacion.schemas import (
    OcupacionDetailResponse,
    OcupacionListResponse,
    OcupacionRecomendacionResponse,
)

router = APIRouter(prefix="/api/occupancy", tags=["Ocupación"])


@router.get("/spaces", response_model=OcupacionListResponse)
async def list_occupancy_spaces():
    """
    Lista todos los espacios de estudio con su ocupación simulada.
    
    @return dict: Objeto con estado, mensaje y la lista de espacios.
    """
    try:
        spaces = service.get_spaces()
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "message": "Error al obtener los espacios de estudio"},
        )

    return {
        "ok": True,
        "message": "Espacios de estudio obtenidos correctamente",
        "data": spaces,
    }


@router.get("/spaces/{space_id}", response_model=OcupacionDetailResponse)
async def get_occupancy_space(space_id: str):
    """
    Obtiene el detalle de ocupación de un espacio específico.
    
    @param space_id: ID del espacio de estudio.
    @return dict: Objeto con estado, mensaje y los detalles del espacio.
    """
    try:
        space = service.get_space_by_id(space_id)
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "message": "Error al obtener el espacio de estudio"},
        )

    if not space:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "message": f"No se encontró el espacio con id '{space_id}'"},
        )

    return {
        "ok": True,
        "message": "Ocupación del espacio obtenida correctamente",
        "data": space,
    }


@router.get("/recommendation", response_model=OcupacionRecomendacionResponse)
async def get_occupancy_recommendation():
    """
    Genera y devuelve una recomendación inteligente de espacio de estudio disponible.
    
    @return dict: Objeto con estado, mensaje y los detalles de la recomendación.
    """
    try:
        recommendation = service.get_recommendation()
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "message": "Error al generar la recomendación"},
        )

    if not recommendation:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "message": "No hay espacios disponibles para recomendar en este momento"},
        )

    return {
        "ok": True,
        "message": "Recomendación generada correctamente",
        "data": recommendation,
    }
