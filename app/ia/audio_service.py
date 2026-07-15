from io import BytesIO
from typing import Optional

from fastapi import UploadFile, HTTPException, status
from openai import AsyncOpenAI

from app.ia.openai_client import obtener_cliente_openai


FORMATOS_AUDIO_PERMITIDOS = [
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
]

MAX_AUDIO_MB = 10


async def transcribir_audio(file: UploadFile) -> str:
    if file.content_type not in FORMATOS_AUDIO_PERMITIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de audio no permitido. Usa mp3, m4a, wav, ogg o webm.",
        )

    audio_bytes = await file.read()

    if len(audio_bytes) > MAX_AUDIO_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El audio es demasiado pesado. Máximo permitido: {MAX_AUDIO_MB} MB.",
        )

    audio_file = BytesIO(audio_bytes)
    audio_file.name = file.filename or "audio_axis.m4a"

    client: AsyncOpenAI = obtener_cliente_openai()

    try:
        transcripcion = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="es",
        )
    except Exception as error:
        print("ERROR TRANSCRIBIENDO AUDIO:", repr(error))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo transcribir el audio con OpenAI.",
        )

    texto_transcrito = transcripcion.text.strip()

    if not texto_transcrito:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo transcribir el audio.",
        )

    return texto_transcrito