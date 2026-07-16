from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from typing import Optional

from app.usuarios.utils import obtener_usuario_actual
from app.ia.service import procesar_solicitud_axis_service


router = APIRouter(prefix="/ia", tags=["IA & Procesamiento"])


@router.post(
    "/procesar-solicitud",
    status_code=status.HTTP_201_CREATED,
    summary="Procesar solicitud con IA mediante texto o audio",
)
async def procesar_solicitud_axis(
    file: Optional[UploadFile] = File(None),
    texto_chat: Optional[str] = Form(None),
    duracion_segundos: Optional[float] = Form(None),
    usuario_actual: dict = Depends(obtener_usuario_actual),
):
    if not file and not texto_chat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes proporcionar al menos un archivo de audio o un texto de chat.",
        )

    if file and duracion_segundos and duracion_segundos > 60:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El audio no puede durar más de 1 minuto.",
        )

    return await procesar_solicitud_axis_service(
        file=file,
        texto_chat=texto_chat,
        usuario_actual=usuario_actual,
    )