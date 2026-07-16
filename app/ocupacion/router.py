from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from app.ocupacion import service, vision_client
from app.ocupacion.schemas import (
    OcupacionDetailResponse,
    OcupacionListResponse,
    OcupacionRecomendacionResponse,
)

router = APIRouter(prefix="/ocupacion", tags=["Ocupación"])


@router.get("/spaces", response_model=OcupacionListResponse)
async def list_occupancy_spaces():
    """
    Lista todos los espacios de estudio, combinados con el último análisis
    automático del vision-service cuando esté disponible.

    @return dict: Objeto con estado, mensaje y la lista de espacios.
    """
    try:
        spaces = await service.get_spaces()
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
        space = await service.get_space_by_id(space_id)
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
        recommendation = await service.get_recommendation()
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


@router.get("/spaces/{space_id}/frame")
async def get_occupancy_space_frame(space_id: str):
    """
    Devuelve la última foto anotada (con las cajas de detección de personas
    dibujadas) del espacio, para que la app pueda mostrar visualmente que el
    tracking es real. Solo existe para espacios con cámara IP conectada.

    @param space_id: ID del espacio de estudio.
    @return: imagen JPEG, o 404 si el espacio no tiene cámara real o aún no se capturó ningún frame.
    """
    frame_bytes = await vision_client.get_latest_frame(space_id)
    if frame_bytes is None:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "message": f"No hay una imagen analizada disponible para '{space_id}'"},
        )

    return Response(content=frame_bytes, media_type="image/jpeg")
