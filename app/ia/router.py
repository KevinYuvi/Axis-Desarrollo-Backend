from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from datetime import datetime, timedelta
from typing import Optional
from io import BytesIO
import json
import os
import re

from bson import ObjectId
from bson.errors import InvalidId
from openai import AsyncOpenAI

from app.database import db
from app.usuarios.utils import obtener_usuario_actual


router = APIRouter(prefix="/ia", tags=["IA & Procesamiento"])

coleccion_reservas = db["reservas"]
coleccion_espacios = db["espacios"]
coleccion_reportes = db["reportes"]


def obtener_cliente_openai() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No está configurada la variable OPENAI_API_KEY en el backend.",
        )

    return AsyncOpenAI(api_key=api_key)


def obtener_hora_ecuador() -> datetime:
    return datetime.utcnow() - timedelta(hours=5)


def obtener_usuario_id(usuario_actual: dict) -> str:
    usuario_id = (
        usuario_actual.get("_id")
        or usuario_actual.get("id")
        or usuario_actual.get("sub")
    )

    if not usuario_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo determinar el ID del usuario desde el token",
        )

    return str(usuario_id)


def obtener_nombre_usuario(usuario_actual: dict) -> str:
    return (
        usuario_actual.get("nombre")
        or usuario_actual.get("nombre_completo")
        or usuario_actual.get("email")
        or "Usuario AXIS"
    )


def obtener_rol_usuario(usuario_actual: dict) -> str:
    rol = (
        usuario_actual.get("rol")
        or usuario_actual.get("role")
        or usuario_actual.get("tipo_usuario")
        or ""
    )

    return str(rol).lower()


def obtener_object_id(id_valor: str) -> ObjectId:
    try:
        return ObjectId(id_valor)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id enviado no tiene un formato válido de MongoDB",
        )


def limpiar_regex(texto: str) -> str:
    return re.escape(texto.strip())


async def transcribir_audio(file: UploadFile) -> str:
    client = obtener_cliente_openai()

    formatos_permitidos = [
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

    if file.content_type not in formatos_permitidos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de audio no permitido. Usa mp3, m4a, wav, ogg o webm.",
        )

    audio_bytes = await file.read()

    max_size_mb = 10

    if len(audio_bytes) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El audio es demasiado pesado. Máximo permitido: {max_size_mb} MB.",
        )

    audio_file = BytesIO(audio_bytes)
    audio_file.name = file.filename or "audio_axis.m4a"

    try:
        transcripcion = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="es",
        )
    except Exception as error:
        print("ERROR TRANSCRIBIENDO AUDIO:", error)
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


async def analizar_solicitud_con_ia(texto_usuario: str, rol_usuario: str) -> dict:
    client = obtener_cliente_openai()

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "accion": {
                "type": "string",
                "enum": ["REPORTE", "CONSULTA", "OTRO"],
            },
            "descripcion_limpia": {
                "type": "string",
            },
            "gravedad": {
                "type": "string",
                "enum": ["baja", "media", "alta"],
            },
            "nombre_aula": {
                "type": ["string", "null"],
            },
            "respuesta_natural": {
                "type": "string",
            },
        },
        "required": [
            "accion",
            "descripcion_limpia",
            "gravedad",
            "nombre_aula",
            "respuesta_natural",
        ],
    }

    try:
        response = await client.responses.create(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "system",
                    "content": (
                        "Eres el asistente IA de AXIS, una app para gestión de aulas. "
                        "Tu tarea es clasificar solicitudes de usuarios. "
                        "Si el usuario reporta un daño, problema técnico, daño físico, falta de equipos, "
                        "proyector dañado, computadora dañada, aire acondicionado, sillas, mesas, luces, "
                        "internet o cualquier incidencia de aula, usa accion REPORTE. "
                        "Si el usuario pregunta por horarios, disponibilidad, ubicación o información general, usa CONSULTA. "
                        "Si no se entiende la intención, usa OTRO. "
                        "La gravedad baja es para problemas menores. "
                        "La gravedad media es para problemas que dificultan la clase. "
                        "La gravedad alta es para problemas que impiden usar el aula o representan riesgo. "
                        "Si el usuario menciona un aula o laboratorio, extrae su nombre en nombre_aula. "
                        "Responde siempre en español ecuatoriano, claro y breve."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Rol del usuario: {rol_usuario}\nSolicitud: {texto_usuario}",
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "axis_solicitud",
                    "schema": schema,
                    "strict": True,
                }
            },
        )

        return json.loads(response.output_text)

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="La IA no devolvió un JSON válido.",
        )

    except Exception as error:
        print("ERROR ANALIZANDO SOLICITUD CON IA:", error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo analizar la solicitud con IA.",
        )


async def buscar_clase_activa_docente(usuario_id: str) -> Optional[dict]:
    ahora = obtener_hora_ecuador()

    reserva = await coleccion_reservas.find_one(
        {
            "usuario_id": usuario_id,
            "hora_inicio": {"$lte": ahora},
            "hora_fin": {"$gte": ahora},
        }
    )

    return reserva


async def buscar_aula_por_nombre(nombre_aula: Optional[str]) -> Optional[dict]:
    if not nombre_aula:
        return None

    nombre_limpio = limpiar_regex(nombre_aula)

    aula = await coleccion_espacios.find_one(
        {
            "nombre": {
                "$regex": nombre_limpio,
                "$options": "i",
            }
        }
    )

    if aula:
        return aula

    aula = await coleccion_espacios.find_one(
        {
            "nombre": {
                "$regex": nombre_limpio.replace("\\ ", ".*"),
                "$options": "i",
            }
        }
    )

    return aula


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
    usuario_id = obtener_usuario_id(usuario_actual)
    rol_usuario = obtener_rol_usuario(usuario_actual)
    nombre_usuario = obtener_nombre_usuario(usuario_actual)

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

    texto_final = ""

    if texto_chat and texto_chat.strip():
        texto_final = texto_chat.strip()

    if file:
        texto_transcrito = await transcribir_audio(file)

        if texto_final:
            texto_final = f"{texto_final}\n\nTranscripción del audio: {texto_transcrito}"
        else:
            texto_final = texto_transcrito

    if not texto_final.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se obtuvo texto válido para procesar.",
        )

    data_ia = await analizar_solicitud_con_ia(texto_final, rol_usuario)

    accion = data_ia.get("accion")
    gravedad = (data_ia.get("gravedad") or "baja").lower()

    if gravedad not in ["baja", "media", "alta"]:
        gravedad = "baja"

    documento_creado_id = None
    espacio_id_vinculado = None
    nombre_aula_final = None

    if accion == "REPORTE":
        if rol_usuario == "estudiante":
            return {
                "status": "error",
                "accion": accion,
                "db_registro_id": None,
                "origen_peticion": texto_final,
                "aula_identificada": None,
                "espacio_id_asociado": None,
                "respuesta_app": (
                    "Como estudiante, puedes consultar información, pero los reportes "
                    "de daños deben ser realizados por un docente o administrador."
                ),
            }

        if rol_usuario not in ["docente", "profesor", "admin", "ayudante"]:
            return {
                "status": "error",
                "accion": accion,
                "db_registro_id": None,
                "origen_peticion": texto_final,
                "aula_identificada": None,
                "espacio_id_asociado": None,
                "respuesta_app": "Tu rol no tiene permisos para generar reportes de incidencias.",
            }

        clase_activa = await buscar_clase_activa_docente(usuario_id)

        if clase_activa:
            espacio_id_vinculado = clase_activa.get("espacio_id")

            try:
                espacio_object_id = obtener_object_id(espacio_id_vinculado)
                aula_db = await coleccion_espacios.find_one({"_id": espacio_object_id})

                if aula_db:
                    nombre_aula_final = aula_db.get("nombre", "Aula asignada por horario")
                else:
                    nombre_aula_final = "Aula asignada por horario"

            except HTTPException:
                espacio_id_vinculado = None
                nombre_aula_final = None

        if not espacio_id_vinculado:
            nombre_aula_detectado = data_ia.get("nombre_aula")
            aula_db = await buscar_aula_por_nombre(nombre_aula_detectado)

            if aula_db:
                espacio_id_vinculado = str(aula_db["_id"])
                nombre_aula_final = aula_db.get("nombre", "Aula identificada")

        if not espacio_id_vinculado:
            return {
                "status": "requiere_informacion",
                "accion": accion,
                "db_registro_id": None,
                "origen_peticion": texto_final,
                "aula_identificada": None,
                "espacio_id_asociado": None,
                "respuesta_app": (
                    "No identifiqué una reserva activa ni el aula en tu mensaje. "
                    "Indícame el nombre del aula o laboratorio para generar el ticket."
                ),
            }

        descripcion_limpia = data_ia.get("descripcion_limpia") or texto_final

        if len(descripcion_limpia.strip()) < 10:
            descripcion_limpia = f"Reporte generado por IA: {texto_final}"

        nuevo_reporte = {
            "espacio_id": espacio_id_vinculado,
            "espacio_nombre": nombre_aula_final,
            "descripcion": descripcion_limpia.strip(),
            "gravedad": gravedad,
            "fecha_reporte": obtener_hora_ecuador(),
            "estado": "abierto",
            "usuario_id": usuario_id,
            "docente_nombre": nombre_usuario,
            "origen": "ia_audio" if file else "ia_texto",
            "texto_original": texto_final,
        }

        resultado = await coleccion_reportes.insert_one(nuevo_reporte)
        documento_creado_id = str(resultado.inserted_id)

        return {
            "status": "success",
            "accion": accion,
            "db_registro_id": documento_creado_id,
            "origen_peticion": texto_final,
            "aula_identificada": nombre_aula_final,
            "espacio_id_asociado": espacio_id_vinculado,
            "respuesta_app": (
                data_ia.get("respuesta_natural")
                or f"Listo, registré el reporte para {nombre_aula_final}."
            ),
        }

    if accion == "CONSULTA":
        return {
            "status": "success",
            "accion": accion,
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": data_ia.get("nombre_aula"),
            "espacio_id_asociado": None,
            "respuesta_app": (
                data_ia.get("respuesta_natural")
                or "Puedo ayudarte con consultas sobre aulas, horarios o disponibilidad."
            ),
        }

    return {
        "status": "requiere_informacion",
        "accion": accion,
        "db_registro_id": None,
        "origen_peticion": texto_final,
        "aula_identificada": data_ia.get("nombre_aula"),
        "espacio_id_asociado": None,
        "respuesta_app": (
            data_ia.get("respuesta_natural")
            or "No entendí completamente la solicitud. Intenta explicarla con más detalle."
        ),
    }