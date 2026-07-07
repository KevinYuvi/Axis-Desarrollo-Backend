import os
from typing import List

import httpx

# URL del vision-service. Escenarios típicos:
# - backend y vision-service locales:      http://localhost:8001
# - backend en Docker, vision-service local: http://host.docker.internal:8001
# - ambos en docker-compose:                 http://vision-service:8001
VISION_SERVICE_URL = os.getenv("VISION_SERVICE_URL", "http://localhost:8001")

# GET /vision/latest solo lee un valor en memoria (el scheduler ya hizo el
# trabajo pesado de antemano), así que debe responder casi al instante. Un
# timeout corto aquí evita que una consulta normal del usuario se sienta
# lenta si el vision-service no responde.
REQUEST_TIMEOUT_SECONDS = 3.0

# Cliente HTTP reutilizado entre llamadas (evita reabrir la conexión TCP en
# cada consulta); es seguro compartirlo porque FastAPI corre en un solo loop.
_http_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)


async def get_latest_snapshots() -> List[dict]:
    """
    Consulta el último análisis automático (Fase 3) de todos los espacios en
    el vision-service. Nunca lanza: cualquier error de red, timeout o
    respuesta inválida se atrapa aquí y se traduce a una lista vacía, para
    que quien llama use el fallback de Fase 1 sin romper la petición.

    @return: lista de snapshots de GET /vision/latest, o [] si no respondió
    """
    try:
        response = await _http_client.get(f"{VISION_SERVICE_URL}/vision/latest")
        response.raise_for_status()
        return response.json()
    except Exception:
        return []
