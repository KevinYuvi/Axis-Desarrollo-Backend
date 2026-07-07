import os
from typing import Optional

import httpx

# URL del vision-service. Escenarios típicos:
# - backend y vision-service locales:      http://localhost:8001
# - backend en Docker, vision-service local: http://host.docker.internal:8001
# - ambos en docker-compose:                 http://vision-service:8001
VISION_SERVICE_URL = os.getenv("VISION_SERVICE_URL", "http://localhost:8001")

# Generoso a propósito: la primera detección con YOLO puede tardar varios
# segundos (carga del modelo en frío, posible descarga de pesos). Un timeout
# corto aquí haría caer al fallback de Fase 1 incluso con el vision-service
# sano, solo por lentitud en el arranque.
REQUEST_TIMEOUT_SECONDS = 15.0

# Cliente HTTP reutilizado entre llamadas (evita reabrir la conexión TCP en
# cada análisis); es seguro compartirlo porque FastAPI corre en un solo loop.
_http_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)


async def request_analysis(analyze_payload: dict) -> Optional[dict]:
    """
    Solicita al vision-service el análisis de ocupación de un espacio.
    Nunca lanza: cualquier error de red, timeout o respuesta inválida se
    atrapa aquí y se traduce a None, para que quien llama decida usar el
    fallback de Fase 1 sin romper la petición del usuario.

    @param analyze_payload: cuerpo esperado por POST /vision/analyze
    @return: diccionario "data" devuelto por el vision-service, o None si no respondió
    """
    try:
        response = await _http_client.post(f"{VISION_SERVICE_URL}/vision/analyze", json=analyze_payload)
        response.raise_for_status()
        response_body = response.json()
        return response_body.get("data")
    except Exception:
        return None
