import json
import os
import time
from typing import Optional

from fastapi import HTTPException, status

from app.ia.openai_client import obtener_cliente_openai
from app.ia.state import (
    obtener_cache_ia,
    guardar_cache_ia,
    obtener_cache_aula,
    guardar_cache_aula,
)
from app.ia.text_utils import normalizar_texto, truncar_para_ia


MODELO_CLASIFICACION_IA = os.getenv("OPENAI_CLASSIFIER_MODEL", "gpt-4o-mini")
MAX_OUTPUT_TOKENS_IA = 300


async def analizar_solicitud_con_ia(texto_usuario: str, rol_usuario: str) -> dict:
    client = obtener_cliente_openai()
    texto_para_ia = truncar_para_ia(texto_usuario)

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
            model=MODELO_CLASIFICACION_IA,
            max_output_tokens=MAX_OUTPUT_TOKENS_IA,
            temperature=0,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Eres el clasificador de AXIS. "
                        "Clasifica la solicitud en REPORTE, CONSULTA u OTRO. "
                        "REPORTE significa daño, falla o incidencia en un aula. "
                        "CONSULTA significa preguntar por horarios, aulas, reservas, disponibilidad o ubicación. "
                        "OTRO significa que no queda claro. "
                        "Extrae nombre_aula solo si aparece explícitamente. "
                        "No inventes aulas. "
                        "Devuelve solo JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Rol: {rol_usuario}\nSolicitud: {texto_para_ia}",
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
        print("ERROR ANALIZANDO SOLICITUD CON IA:", repr(error))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo analizar la solicitud con IA.",
        )


async def analizar_solicitud_con_ia_cacheado(texto_usuario: str, rol_usuario: str) -> dict:
    texto_cache = truncar_para_ia(texto_usuario)
    clave = f"{rol_usuario}:{normalizar_texto(texto_cache)}"

    cache = obtener_cache_ia(clave)

    if cache:
        print("IA CACHE HIT:", clave)
        return cache

    print("IA CACHE MISS:", clave)

    resultado = await analizar_solicitud_con_ia(
        texto_usuario=texto_usuario,
        rol_usuario=rol_usuario,
    )

    guardar_cache_ia(clave, resultado)

    return resultado


async def extraer_aula_con_ia_cacheado(texto_usuario: str) -> Optional[str]:
    texto_cache = truncar_para_ia(texto_usuario)
    clave = normalizar_texto(texto_cache)

    cache = obtener_cache_aula(clave)

    if cache is not None:
        print("EXTRAER AULA CACHE HIT:", clave)
        return cache

    print("EXTRAER AULA CACHE MISS:", clave)

    client = obtener_cliente_openai()

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "nombre_aula": {
                "type": ["string", "null"],
            }
        },
        "required": ["nombre_aula"],
    }

    try:
        response = await client.responses.create(
            model=MODELO_CLASIFICACION_IA,
            max_output_tokens=80,
            temperature=0,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Extrae solo el aula, sala o laboratorio mencionado. "
                        "No agregues letras si no estás seguro. "
                        "Si el texto parece decir 'aula 5 desde', devuelve 'Aula 5', no 'Aula 5D'. "
                        "Si no existe aula explícita, devuelve null. Solo JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": texto_cache,
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "axis_extraer_aula",
                    "schema": schema,
                    "strict": True,
                }
            },
        )

        data = json.loads(response.output_text)
        resultado = data.get("nombre_aula")

        guardar_cache_aula(clave, resultado)

        return resultado

    except Exception as error:
        print("ERROR EXTRAYENDO AULA CON IA:", repr(error))
        guardar_cache_aula(clave, None)
        return None