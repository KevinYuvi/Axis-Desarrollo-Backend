import time
from typing import Optional

TTL_CACHE_IA_SEGUNDOS = 180
TTL_RESERVA_PENDIENTE_SEGUNDOS = 300
INTERVALO_LIMPIEZA_CACHE_SEGUNDOS = 600

_cache_ia = {}
_cache_extraer_aula = {}
_reservas_pendientes = {}

_ultima_limpieza_cache = time.time()


def guardar_reserva_pendiente(usuario_id: str, data: dict) -> None:
    _reservas_pendientes[usuario_id] = {
        "timestamp": time.time(),
        "data": data,
    }


def obtener_reserva_pendiente(usuario_id: str) -> Optional[dict]:
    pendiente = _reservas_pendientes.get(usuario_id)

    if not pendiente:
        return None

    timestamp = pendiente.get("timestamp", 0)

    if time.time() - timestamp > TTL_RESERVA_PENDIENTE_SEGUNDOS:
        _reservas_pendientes.pop(usuario_id, None)
        return None

    return pendiente.get("data")


def eliminar_reserva_pendiente(usuario_id: str) -> None:
    _reservas_pendientes.pop(usuario_id, None)


def obtener_cache_ia(clave: str):
    item = _cache_ia.get(clave)

    if not item:
        return None

    timestamp, resultado = item

    if time.time() - timestamp >= TTL_CACHE_IA_SEGUNDOS:
        _cache_ia.pop(clave, None)
        return None

    return resultado


def guardar_cache_ia(clave: str, resultado: dict) -> None:
    _cache_ia[clave] = (time.time(), resultado)


def obtener_cache_aula(clave: str):
    item = _cache_extraer_aula.get(clave)

    if not item:
        return None

    timestamp, resultado = item

    if time.time() - timestamp >= TTL_CACHE_IA_SEGUNDOS:
        _cache_extraer_aula.pop(clave, None)
        return None

    return resultado


def guardar_cache_aula(clave: str, resultado) -> None:
    _cache_extraer_aula[clave] = (time.time(), resultado)


def limpiar_caches_si_corresponde() -> None:
    global _ultima_limpieza_cache

    ahora = time.time()

    if ahora - _ultima_limpieza_cache < INTERVALO_LIMPIEZA_CACHE_SEGUNDOS:
        return

    _limpiar_cache_vencido(_cache_ia, TTL_CACHE_IA_SEGUNDOS)
    _limpiar_cache_vencido(_cache_extraer_aula, TTL_CACHE_IA_SEGUNDOS)
    _limpiar_reservas_pendientes_vencidas()

    _ultima_limpieza_cache = ahora


def _limpiar_cache_vencido(cache: dict, ttl: int) -> None:
    ahora = time.time()

    claves_vencidas = [
        clave
        for clave, (timestamp, _) in cache.items()
        if ahora - timestamp >= ttl
    ]

    for clave in claves_vencidas:
        cache.pop(clave, None)


def _limpiar_reservas_pendientes_vencidas() -> None:
    ahora = time.time()

    claves_vencidas = [
        usuario_id
        for usuario_id, pendiente in _reservas_pendientes.items()
        if ahora - pendiente.get("timestamp", 0) >= TTL_RESERVA_PENDIENTE_SEGUNDOS
    ]

    for usuario_id in claves_vencidas:
        _reservas_pendientes.pop(usuario_id, None)