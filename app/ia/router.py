from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from datetime import datetime, timedelta
from typing import Optional
from io import BytesIO
import json
import os
import re
import time

from bson import ObjectId
from bson.errors import InvalidId
from openai import AsyncOpenAI

from app.database import db
from app.usuarios.utils import obtener_usuario_actual, normalizar_rol


router = APIRouter(prefix="/ia", tags=["IA & Procesamiento"])

# Roles (canónicos) con permiso para ejecutar acciones desde el chat IA
# (reportes, reservas, liberación de aulas). Los alias como "profesor"
# se resuelven con normalizar_rol antes de comparar.
ROLES_CON_ACCIONES = {"docente", "admin", "ayudante"}

coleccion_reservas = db["reservas"]
coleccion_espacios = db["espacios"]
coleccion_reportes = db["reportes"]

MODELO_CLASIFICACION_IA = os.getenv("OPENAI_CLASSIFIER_MODEL", "gpt-4o-mini")
MAX_CHARS_IA = 500
MAX_OUTPUT_TOKENS_IA = 300
TTL_CACHE_IA_SEGUNDOS = 180
TTL_RESERVA_PENDIENTE_SEGUNDOS = 300

_cache_ia = {}
_cache_extraer_aula = {}
_reservas_pendientes = {}

_ultima_limpieza_cache = time.time()
INTERVALO_LIMPIEZA_CACHE_SEGUNDOS = 600


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


def limpiar_caches_si_corresponde() -> None:
    global _ultima_limpieza_cache

    ahora = time.time()

    if ahora - _ultima_limpieza_cache < INTERVALO_LIMPIEZA_CACHE_SEGUNDOS:
        return

    _limpiar_cache_vencido(_cache_ia, TTL_CACHE_IA_SEGUNDOS)
    _limpiar_cache_vencido(_cache_extraer_aula, TTL_CACHE_IA_SEGUNDOS)
    _limpiar_reservas_pendientes_vencidas()

    _ultima_limpieza_cache = ahora


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


def normalizar_texto(texto: str) -> str:
    texto = str(texto or "").lower().strip()
    texto = texto.replace("á", "a")
    texto = texto.replace("é", "e")
    texto = texto.replace("í", "i")
    texto = texto.replace("ó", "o")
    texto = texto.replace("ú", "u")
    texto = texto.replace("ñ", "n")
    texto = texto.replace("-", " ")
    texto = texto.replace("_", " ")
    texto = re.sub(r"[,.;:!¡¿?]", "", texto)  # <-- AGREGAR ESTA LÍNEA
    texto = re.sub(r"\s+", " ", texto)
    return texto


def compactar_texto(texto: str) -> str:
    texto = normalizar_texto(texto)
    texto = texto.replace(" ", "")
    texto = texto.replace(".", "")
    texto = texto.replace(",", "")
    return texto


def limpiar_regex(texto: str) -> str:
    return re.escape(str(texto or "").strip())


def truncar_para_ia(texto: str, max_chars: int = MAX_CHARS_IA) -> str:
    texto = str(texto or "").strip()

    if len(texto) <= max_chars:
        return texto

    return texto[:max_chars] + "..."


def generar_variantes_nombre_aula(nombre_aula: str) -> list:
    if not nombre_aula:
        return []

    nombre = normalizar_texto(nombre_aula)

    variantes = [nombre]

    variantes.append(nombre.replace("laboratorio", "lab"))
    variantes.append(nombre.replace("lab", "laboratorio"))
    variantes.append(nombre.replace("computacion", "comp"))

    variantes.append(nombre.replace(" 3 a", " 3a"))
    variantes.append(nombre.replace(" 2 a", " 2a"))
    variantes.append(nombre.replace(" 1 a", " 1a"))

    variantes.append(nombre.replace("tres a", "3a"))
    variantes.append(nombre.replace("dos a", "2a"))
    variantes.append(nombre.replace("uno a", "1a"))

    partes = nombre.split()

    for parte in partes:
        if re.match(r"^\d+[a-z]$", parte):
            variantes.append(parte)

    return list(set([v.strip() for v in variantes if v.strip()]))


def detectar_consulta_directa(texto: str) -> bool:
    texto = normalizar_texto(texto)

    palabras_consulta = [
        "horario",
        "horarios",
        "clase",
        "clases",
        "reserva",
        "reservas",
        "disponible",
        "disponibilidad",
        "queda",
        "ubicacion",
        "donde",
        "consultar",
        "consulta",
        "libre",
        "ocupada",
        "ocupado",
    ]

    return any(palabra in texto for palabra in palabras_consulta)


def detectar_reporte_directo(texto: str) -> bool:
    texto = normalizar_texto(texto)

    palabras_reporte = [
        "danado",
        "dañado",
        "falla",
        "fallando",
        "no funciona",
        "no enciende",
        "no prende",
        "roto",
        "averiado",
        "problema",
        "incidencia",
        "reportar",
        "reporte",
        "proyector",
        "computadora",
        "internet",
        "luz",
        "luces",
        "aire acondicionado",
        "silla",
        "mesa",
        "pantalla",
        "cable",
        "enchufe",
    ]

    return any(palabra in texto for palabra in palabras_reporte)


def detectar_consulta_espacios_general(texto: str) -> bool:
    texto = normalizar_texto(texto)

    palabras = [
        "cuantas aulas",
        "cuantos aulas",
        "cuantos laboratorios",
        "cuantas salas",
        "que aulas",
        "cuales aulas",
        "aulas disponibles",
        "laboratorios disponibles",
        "espacios disponibles",
        "aulas hay",
        "laboratorios hay",
        "cuantos espacios",
        "cuantos salones",
        "que laboratorios",
    ]

    return any(palabra in texto for palabra in palabras)


def detectar_disponibilidad_por_horario(texto: str) -> bool:
    texto_norm = normalizar_texto(texto)

    palabras = [
        "disponible",
        "disponibles",
        "libre",
        "libres",
        "desocupada",
        "desocupadas",
    ]

    tiene_disponibilidad = any(palabra in texto_norm for palabra in palabras)
    tiene_hora = bool(re.search(r"\d{1,2}\s*(am|pm|a\.m\.|p\.m\.)?", texto_norm))

    return tiene_disponibilidad and tiene_hora


def detectar_solicitud_reserva(texto: str) -> bool:
    texto_norm = normalizar_texto(texto)

    # Evita confundir consultas con creación de reserva
    patrones_consulta_reserva = [
        r"\bque reservas\b",
        r"\bqué reservas\b",
        r"\bver reservas\b",
        r"\bmis reservas\b",
        r"\bconsultar reservas\b",
        r"\bhorario de reservas\b",
        r"\breservas disponibles\b",
        r"\bmostrar reservas\b",
        r"\blistar reservas\b",
    ]

    if any(re.search(patron, texto_norm) for patron in patrones_consulta_reserva):
        return False

    patrones_reserva = [
        # Frases directas
        r"\bquiero reservar\b",
        r"\bquiero una reserva\b",
        r"\bquiero la reserva\b",
        r"\bquiero hacer una reserva\b",
        r"\bhacer una reserva\b",
        r"\bhaz una reserva\b",
        r"\bnecesito reservar\b",
        r"\bnecesito una reserva\b",
        r"\bnecesito la reserva\b",

        # Formas con "generar"
        r"\bgenerar una reserva\b",
        r"\bgenerar la reserva\b",
        r"\bgenerame una reserva\b",
        r"\bgenerame la reserva\b",
        r"\bgeneres una reserva\b",
        r"\bgeneres la reserva\b",
        r"\bme generes una reserva\b",
        r"\bme generes la reserva\b",
        r"\bquiero que me generes una reserva\b",
        r"\bquiero que me generes la reserva\b",

        # Formas con "reservar / reservarme / reserves"
        r"\bme puedes reservar\b",
        r"\bpuedes reservar\b",
        r"\bquiero que me reserves\b",
        r"\bme reserves\b",
        r"\breserves\b",
        r"\breservame\b",
        r"\breservar\b",
        r"\breserva el\b",
        r"\breserva la\b",
        r"\breserva un\b",
        r"\breserva una\b",
        r"\breserva del\b",
        r"\breserva de la\b",
        r"\breserva de un\b",
        r"\breserva de una\b",
        r"\breserva para\b",
        r"\breservalo\b",
        r"\breservala\b",

        # Errores comunes de escritura/transcripción
        r"\breserbame\b",
        r"\breserba\b",
        r"\bserva\b",
        r"\bservserva\b",

        # Sinónimos
        r"\baparta\b",
        r"\bapartar\b",
        r"\bapartame\b",
        r"\bsepara\b",
        r"\bseparar\b",
        r"\bseparame\b",
        r"\bagenda\b",
        r"\bagendar\b",
        r"\bagendame\b",
        r"\bocupar el aula\b",
        r"\bocupar laboratorio\b",
    ]

    return any(re.search(patron, texto_norm) for patron in patrones_reserva)


def detectar_solicitud_liberacion_aula(texto: str) -> bool:
    texto_norm = normalizar_texto(texto)

    patrones_liberacion = [
        r"\bliberar aula\b",
        r"\blibera el aula\b",
        r"\blibera la aula\b",
        r"\blibera mi aula\b",
        r"\bliberar mi aula\b",
        r"\blibera laboratorio\b",
        r"\blibera el laboratorio\b",
        r"\bliberar laboratorio\b",
        r"\bdejar libre\b",
        r"\bdeja libre\b",
        r"\bdesocupar aula\b",
        r"\bdesocupa el aula\b",
        r"\bdesocupar laboratorio\b",
        r"\bya termine\b",
        r"\bya terminé\b",
        r"\btermine la clase\b",
        r"\bterminé la clase\b",
        r"\bfinalice la clase\b",
        r"\bfinalicé la clase\b",
        r"\bsali del aula\b",
        r"\bsalí del aula\b",
        r"\bsali del laboratorio\b",
        r"\bsalí del laboratorio\b",
    ]

    return any(re.search(patron, texto_norm) for patron in patrones_liberacion)

def detectar_confirmacion_reserva(texto: str) -> bool:
    texto_norm = normalizar_texto(texto)

    confirmaciones_exactas = [
        "si",
        "sí",
        "confirmo",
        "confirma",
        "confirmar",
        "dale",
        "ok",
        "listo",
        "acepto",
        "hazlo",
    ]

    if texto_norm in confirmaciones_exactas:
        return True

    patrones = [
        r"\bsi confirma\b",
        r"\bsí confirma\b",
        r"\bconfirmo la reserva\b",
        r"\bconfirmar reserva\b",
        r"\breservalo\b",
        r"\bhaz la reserva\b",
    ]

    return any(re.search(patron, texto_norm) for patron in patrones)


def detectar_cancelacion_reserva(texto: str) -> bool:
    texto_norm = normalizar_texto(texto)

    cancelaciones_exactas = [
        "no",
        "cancela",
        "cancelar",
        "olvida",
        "mejor no",
        "ya no",
    ]

    if texto_norm in cancelaciones_exactas:
        return True

    patrones = [
        r"\bcancela la reserva\b",
        r"\bmejor no\b",
        r"\bya no\b",
        r"\bno la reserves\b",
    ]

    return any(re.search(patron, texto_norm) for patron in patrones)


def extraer_nombre_aula_simple(texto: str) -> Optional[str]:
    texto_norm = normalizar_texto(texto)

    patrones = [
        r"laboratorio\s+de\s+computacion\s+\d+\s*[a-z]?",
        r"laboratorio\s+\d+\s*[a-z]?",
        r"lab\s+\d+\s*[a-z]?",
        r"aula\s+\d+\s*[a-z]?",
        r"salon\s+\d+\s*[a-z]?",
        r"sala\s+\d+\s*[a-z]?",
    ]

    for patron in patrones:
        match = re.search(patron, texto_norm)

        if match:
            return match.group(0)

    return None


def extraer_bloque_o_edificio(texto: str) -> Optional[str]:
    texto_norm = normalizar_texto(texto)

    patrones = [
        r"edificio\s+[a-z0-9]+",
        r"bloque\s+[a-z0-9]+",
    ]

    for patron in patrones:
        match = re.search(patron, texto_norm)

        if match:
            return match.group(0)

    return None


def convertir_hora_a_24(hora_texto: str, periodo: Optional[str]) -> Optional[int]:
    try:
        hora = int(hora_texto)

        if periodo:
            periodo = periodo.lower().replace(".", "")

            if periodo == "pm" and hora != 12:
                hora += 12

            if periodo == "am" and hora == 12:
                hora = 0

        return hora

    except Exception:
        return None


def extraer_rango_horario(texto: str) -> Optional[tuple]:
    texto_norm = normalizar_texto(texto)

    patrones = [
        r"de\s+(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)?\s+a\s+(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)?",
        r"desde\s+(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)?\s+hasta\s+(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)?",
        r"(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)?\s*-\s*(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)?",
    ]

    for patron in patrones:
        match = re.search(patron, texto_norm)

        if match:
            hora_inicio_txt = match.group(1)
            periodo_inicio = match.group(2)
            hora_fin_txt = match.group(3)
            periodo_fin = match.group(4)

            if not periodo_inicio and periodo_fin:
                periodo_inicio = periodo_fin

            hora_inicio = convertir_hora_a_24(hora_inicio_txt, periodo_inicio)
            hora_fin = convertir_hora_a_24(hora_fin_txt, periodo_fin)

            if hora_inicio is None or hora_fin is None:
                return None

            if hora_fin <= hora_inicio:
                return None

            return hora_inicio, hora_fin

    return None


def extraer_materia_reserva(texto: str) -> str:
    texto_norm = normalizar_texto(texto)

    patrones = [
        r"para\s+la\s+clase\s+de\s+(.+)",
        r"para\s+clase\s+de\s+(.+)",
        r"para\s+(.+)",
    ]

    for patron in patrones:
        match = re.search(patron, texto_norm)

        if match:
            materia = match.group(1).strip()

            materia = re.sub(
                r"\s+de\s+\d{1,2}\s*(am|pm)?\s+a\s+\d{1,2}\s*(am|pm)?",
                "",
                materia,
            ).strip()

            if len(materia) >= 3:
                return materia.capitalize()

    return "Reserva generada por asistente IA"


def convertir_espacio_simple(espacio: dict) -> dict:
    return {
        "id": str(espacio.get("_id")),
        "nombre": espacio.get("nombre"),
        "bloque": espacio.get("bloque"),
        "tipo": espacio.get("tipo"),
        "estado_actual": espacio.get("estado_actual"),
        "capacidad": espacio.get("capacidad"),
    }


def formatear_fecha_hora(valor) -> str:
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M")

    try:
        fecha = datetime.fromisoformat(str(valor))
        return fecha.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(valor)


def formatear_solo_hora(valor) -> str:
    if isinstance(valor, datetime):
        return valor.strftime("%H:%M")

    try:
        fecha = datetime.fromisoformat(str(valor))
        return fecha.strftime("%H:%M")
    except Exception:
        return str(valor)


def formatear_horario_reserva(reserva: dict) -> str:
    materia = reserva.get("materia", "Clase registrada")
    docente = reserva.get("docente_nombre", "Docente no registrado")

    hora_inicio = reserva.get("hora_inicio")
    hora_fin = reserva.get("hora_fin")

    inicio_txt = formatear_fecha_hora(hora_inicio)
    fin_txt = formatear_solo_hora(hora_fin)

    return f"{materia}, con {docente}, de {inicio_txt} a {fin_txt}"


def convertir_reserva_simple(reserva: dict) -> dict:
    return {
        "id": str(reserva.get("_id")),
        "materia": reserva.get("materia"),
        "docente_nombre": reserva.get("docente_nombre"),
        "hora_inicio": formatear_fecha_hora(reserva.get("hora_inicio")),
        "hora_fin": formatear_fecha_hora(reserva.get("hora_fin")),
        "usuario_id": reserva.get("usuario_id"),
        "espacio_id": reserva.get("espacio_id"),
    }


def guardar_reserva_pendiente(usuario_id: str, data: dict) -> None:
    _reservas_pendientes[usuario_id] = {
        "timestamp": time.time(),
        "data": data,
    }


def obtener_reserva_pendiente(usuario_id: str) -> Optional[dict]:
    pendiente = _reservas_pendientes.get(usuario_id)

    if not pendiente:
        return None

    timestamp = pendiente.get("timestamp")

    if time.time() - timestamp > TTL_RESERVA_PENDIENTE_SEGUNDOS:
        _reservas_pendientes.pop(usuario_id, None)
        return None

    return pendiente.get("data")


def eliminar_reserva_pendiente(usuario_id: str) -> None:
    _reservas_pendientes.pop(usuario_id, None)


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
                        "Clasifica: REPORTE (daño/falla en aula), "
                        "CONSULTA (horario/ubicación/disponibilidad), "
                        "OTRO (ambiguo). Extrae nombre_aula si aparece. "
                        "Gravedad: baja/media/alta. Solo JSON."
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
        print("ERROR ANALIZANDO SOLICITUD CON IA:", error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo analizar la solicitud con IA.",
        )


async def analizar_solicitud_con_ia_cacheado(texto_usuario: str, rol_usuario: str) -> dict:
    texto_cache = truncar_para_ia(texto_usuario)
    clave = f"{rol_usuario}:{normalizar_texto(texto_cache)}"
    ahora = time.time()

    if clave in _cache_ia:
        timestamp, resultado = _cache_ia[clave]

        if ahora - timestamp < TTL_CACHE_IA_SEGUNDOS:
            print("IA CACHE HIT:", clave)
            return resultado

    print("IA CACHE MISS:", clave)

    resultado = await analizar_solicitud_con_ia(texto_usuario, rol_usuario)
    _cache_ia[clave] = (ahora, resultado)

    return resultado


async def extraer_aula_con_ia_cacheado(texto_usuario: str) -> Optional[str]:
    texto_cache = truncar_para_ia(texto_usuario)
    clave = normalizar_texto(texto_cache)
    ahora = time.time()

    if clave in _cache_extraer_aula:
        timestamp, resultado = _cache_extraer_aula[clave]

        if ahora - timestamp < TTL_CACHE_IA_SEGUNDOS:
            print("EXTRAER AULA CACHE HIT:", clave)
            return resultado

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
                        "Extrae solo el aula o laboratorio mencionado. "
                        "Si no existe, devuelve null. Solo JSON."
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
        _cache_extraer_aula[clave] = (ahora, resultado)

        return resultado

    except Exception as error:
        print("ERROR EXTRAYENDO AULA CON IA:", error)
        return None


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

    nombre_buscado = normalizar_texto(nombre_aula)
    variantes = generar_variantes_nombre_aula(nombre_aula)

    patrones_exactos = list({
        f"^{limpiar_regex(v)}$"
        for v in variantes
        if v
    })

    if patrones_exactos:
        aula = await coleccion_espacios.find_one(
            {
                "nombre": {
                    "$regex": "|".join(patrones_exactos),
                    "$options": "i",
                }
            }
        )

        if aula:
            return aula

    patrones_parciales = list({
        limpiar_regex(v)
        for v in variantes
        if v
    })

    if patrones_parciales:
        aula = await coleccion_espacios.find_one(
            {
                "nombre": {
                    "$regex": "|".join(patrones_parciales),
                    "$options": "i",
                }
            }
        )

        if aula:
            return aula

    palabras = [
        palabra
        for palabra in nombre_buscado.split()
        if palabra not in [
            "el",
            "la",
            "de",
            "del",
            "en",
            "aula",
            "laboratorio",
            "lab",
        ]
    ]

    if palabras:
        filtro_and = {
            "$and": [
                {
                    "nombre": {
                        "$regex": limpiar_regex(palabra),
                        "$options": "i",
                    }
                }
                for palabra in palabras
            ]
        }

        aula = await coleccion_espacios.find_one(filtro_and)

        if aula:
            return aula

    nombre_buscado_compacto = compactar_texto(nombre_aula)

    if nombre_buscado_compacto:
        cursor = coleccion_espacios.find({}, {"_id": 1, "nombre": 1})

        async for espacio in cursor:
            nombre_db_compacto = compactar_texto(espacio.get("nombre", ""))

            if nombre_db_compacto and (
                nombre_buscado_compacto == nombre_db_compacto
                or nombre_buscado_compacto in nombre_db_compacto
            ):
                return await coleccion_espacios.find_one({"_id": espacio["_id"]})

    return None


async def buscar_horarios_de_aula(espacio_id: str, limite: int = 5) -> list:
    ahora = obtener_hora_ecuador()

    cursor = coleccion_reservas.find(
        {
            "espacio_id": espacio_id,
            "hora_fin": {"$gte": ahora},
        }
    ).sort("hora_inicio", 1).limit(limite)

    horarios = []

    async for reserva in cursor:
        horarios.append(reserva)

    return horarios


async def verificar_conflicto_reserva(
    espacio_id: str,
    hora_inicio: datetime,
    hora_fin: datetime,
) -> Optional[dict]:
    reserva_en_conflicto = await coleccion_reservas.find_one(
        {
            "espacio_id": espacio_id,
            "hora_inicio": {"$lt": hora_fin},
            "hora_fin": {"$gt": hora_inicio},
        }
    )

    return reserva_en_conflicto


async def verificar_disponibilidad_actual_aula(espacio_id: str) -> tuple:
    ahora = obtener_hora_ecuador()

    reserva_activa = await coleccion_reservas.find_one(
        {
            "espacio_id": espacio_id,
            "hora_inicio": {"$lte": ahora},
            "hora_fin": {"$gte": ahora},
        }
    )

    return reserva_activa is None, reserva_activa


async def resolver_disponibilidad_aula_especifica(texto_final: str) -> Optional[dict]:
    texto_norm = normalizar_texto(texto_final)

    palabras_disponibilidad = [
        "disponible",
        "disponibles",
        "libre",
        "libres",
        "ocupada",
        "ocupado",
    ]

    if not any(palabra in texto_norm for palabra in palabras_disponibilidad):
        return None

    nombre_aula_detectado = extraer_nombre_aula_simple(texto_final)

    if not nombre_aula_detectado:
        return None

    aula_db = await buscar_aula_por_nombre(nombre_aula_detectado)

    if not aula_db:
        return None

    espacio_id = str(aula_db["_id"])
    nombre_aula = aula_db.get("nombre", "Aula identificada")

    esta_libre, reserva_activa = await verificar_disponibilidad_actual_aula(espacio_id)

    if esta_libre:
        respuesta_app = f"Sí, el {nombre_aula} está disponible en este momento."
    else:
        materia = reserva_activa.get("materia", "una clase")
        fin_txt = formatear_solo_hora(reserva_activa.get("hora_fin"))

        respuesta_app = (
            f"No, el {nombre_aula} está ocupado ahora mismo con {materia} "
            f"hasta las {fin_txt}."
        )

    return {
        "status": "success",
        "accion": "CONSULTA",
        "db_registro_id": None,
        "origen_peticion": texto_final,
        "aula_identificada": nombre_aula,
        "espacio_id_asociado": espacio_id,
        "disponible_ahora": esta_libre,
        "respuesta_app": respuesta_app,
        "detalle_aula": {
            "nombre": nombre_aula,
            "bloque": aula_db.get("bloque"),
            "tipo": aula_db.get("tipo"),
            "estado_actual": aula_db.get("estado_actual"),
        },
    }


async def resolver_disponibilidad_por_horario(texto_final: str) -> Optional[dict]:
    if not detectar_disponibilidad_por_horario(texto_final):
        return None

    rango = extraer_rango_horario(texto_final)

    if not rango:
        return None

    hora_inicio, hora_fin = rango

    ahora = obtener_hora_ecuador()
    fecha_consulta = ahora.date()

    inicio = datetime(
        fecha_consulta.year,
        fecha_consulta.month,
        fecha_consulta.day,
        hora_inicio,
        0,
        0,
    )

    fin = datetime(
        fecha_consulta.year,
        fecha_consulta.month,
        fecha_consulta.day,
        hora_fin,
        0,
        0,
    )

    cursor_espacios = coleccion_espacios.find({}).sort("nombre", 1)

    espacios = []

    async for espacio in cursor_espacios:
        espacios.append(espacio)

    disponibles = []

    for espacio in espacios:
        espacio_id = str(espacio["_id"])

        reserva_en_conflicto = await verificar_conflicto_reserva(
            espacio_id=espacio_id,
            hora_inicio=inicio,
            hora_fin=fin,
        )

        if not reserva_en_conflicto:
            disponibles.append(espacio)

    if not disponibles:
        return {
            "status": "success",
            "accion": "CONSULTA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": None,
            "espacio_id_asociado": None,
            "respuesta_app": (
                f"No encontré aulas disponibles hoy de {hora_inicio:02d}:00 a {hora_fin:02d}:00."
            ),
            "espacios": [],
        }

    respuesta = (
        f"Encontré {len(disponibles)} aula(s) disponible(s) hoy "
        f"de {hora_inicio:02d}:00 a {hora_fin:02d}:00:\n\n"
    )

    for index, espacio in enumerate(disponibles[:8], start=1):
        nombre = espacio.get("nombre", "Espacio sin nombre")
        bloque = espacio.get("bloque", "Sin bloque")

        respuesta += f"{index}. {nombre} - {bloque}\n"

    if len(disponibles) > 8:
        respuesta += f"\nY {len(disponibles) - 8} espacio(s) más."

    return {
        "status": "success",
        "accion": "CONSULTA",
        "db_registro_id": None,
        "origen_peticion": texto_final,
        "aula_identificada": None,
        "espacio_id_asociado": None,
        "respuesta_app": respuesta.strip(),
        "espacios": [convertir_espacio_simple(espacio) for espacio in disponibles],
    }


async def resolver_consulta_espacios_general(texto_final: str) -> Optional[dict]:
    if not detectar_consulta_espacios_general(texto_final):
        return None

    texto_norm = normalizar_texto(texto_final)
    bloque_detectado = extraer_bloque_o_edificio(texto_final)

    filtro = {}

    if bloque_detectado:
        bloque_limpio = normalizar_texto(bloque_detectado)
        bloque_valor = (
            bloque_limpio.replace("edificio", "")
            .replace("bloque", "")
            .strip()
        )

        filtro["$or"] = [
            {"bloque": {"$regex": bloque_valor, "$options": "i"}},
            {"nombre": {"$regex": bloque_valor, "$options": "i"}},
        ]

    if "disponible" in texto_norm or "disponibles" in texto_norm:
        filtro["estado_actual"] = {"$regex": "disponible", "$options": "i"}

    cursor = coleccion_espacios.find(filtro).sort("nombre", 1)

    espacios = []

    async for espacio in cursor:
        espacios.append(espacio)

    total = len(espacios)

    if total == 0:
        return {
            "status": "success",
            "accion": "CONSULTA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": None,
            "espacio_id_asociado": None,
            "respuesta_app": "No encontré aulas o laboratorios registrados con esos criterios.",
            "espacios": [],
        }

    nombres = [espacio.get("nombre", "Espacio sin nombre") for espacio in espacios[:8]]

    if "cuantas" in texto_norm or "cuantos" in texto_norm:
        if bloque_detectado:
            respuesta = f"Encontré {total} espacio(s) registrado(s) en {bloque_detectado}."
        else:
            respuesta = f"Encontré {total} espacio(s) registrado(s) en total."

        respuesta += "\n\nAlgunos son:\n"

        for index, nombre in enumerate(nombres, start=1):
            respuesta += f"{index}. {nombre}\n"

        return {
            "status": "success",
            "accion": "CONSULTA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": None,
            "espacio_id_asociado": None,
            "respuesta_app": respuesta.strip(),
            "espacios": [convertir_espacio_simple(espacio) for espacio in espacios],
        }

    respuesta = "Encontré estos espacios:\n\n"

    for index, espacio in enumerate(espacios[:8], start=1):
        nombre = espacio.get("nombre", "Espacio sin nombre")
        bloque = espacio.get("bloque", "Sin bloque")
        estado = espacio.get("estado_actual", "Sin estado")

        respuesta += f"{index}. {nombre} - {bloque} - {estado}\n"

    if total > 8:
        respuesta += f"\nY {total - 8} espacio(s) más."

    return {
        "status": "success",
        "accion": "CONSULTA",
        "db_registro_id": None,
        "origen_peticion": texto_final,
        "aula_identificada": None,
        "espacio_id_asociado": None,
        "respuesta_app": respuesta.strip(),
        "espacios": [convertir_espacio_simple(espacio) for espacio in espacios],
    }


async def resolver_consulta_directa(texto_final: str) -> Optional[dict]:
    nombre_aula_detectado = extraer_nombre_aula_simple(texto_final)
    es_consulta = detectar_consulta_directa(texto_final)
    es_reporte = detectar_reporte_directo(texto_final)

    if not es_consulta and not nombre_aula_detectado:
        return None

    if es_reporte:
        return None

    if not nombre_aula_detectado:
        return None

    aula_db = await buscar_aula_por_nombre(nombre_aula_detectado)

    if not aula_db:
        return {
            "status": "requiere_informacion",
            "accion": "CONSULTA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": nombre_aula_detectado,
            "espacio_id_asociado": None,
            "respuesta_app": (
                "No pude identificar con seguridad el aula o laboratorio. "
                "Indícame el nombre completo, por ejemplo: Laboratorio de Computación 3."
            ),
        }

    espacio_id = str(aula_db["_id"])
    nombre_aula = aula_db.get("nombre", "Aula identificada")

    horarios = await buscar_horarios_de_aula(espacio_id)

    if not horarios:
        return {
            "status": "success",
            "accion": "CONSULTA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": nombre_aula,
            "espacio_id_asociado": espacio_id,
            "horarios": [],
            "respuesta_app": (
                f"Encontré el {nombre_aula}. "
                "No tiene reservas próximas registradas por el momento."
            ),
            "detalle_aula": {
                "nombre": nombre_aula,
                "bloque": aula_db.get("bloque"),
                "tipo": aula_db.get("tipo"),
                "estado_actual": aula_db.get("estado_actual"),
            },
        }

    respuesta = f"Encontré estos horarios próximos para {nombre_aula}:\n\n"

    for index, reserva in enumerate(horarios, start=1):
        respuesta += f"{index}. {formatear_horario_reserva(reserva)}\n"

    return {
        "status": "success",
        "accion": "CONSULTA",
        "db_registro_id": None,
        "origen_peticion": texto_final,
        "aula_identificada": nombre_aula,
        "espacio_id_asociado": espacio_id,
        "horarios": [convertir_reserva_simple(reserva) for reserva in horarios],
        "respuesta_app": respuesta.strip(),
        "detalle_aula": {
            "nombre": nombre_aula,
            "bloque": aula_db.get("bloque"),
            "tipo": aula_db.get("tipo"),
            "estado_actual": aula_db.get("estado_actual"),
        },
    }


async def crear_reporte(
    texto_final: str,
    usuario_id: str,
    nombre_usuario: str,
    espacio_id_vinculado: str,
    nombre_aula_final: str,
    gravedad: str,
    file: Optional[UploadFile],
) -> dict:
    if gravedad not in ["baja", "media", "alta"]:
        gravedad = "media"

    descripcion_limpia = texto_final.strip()

    if len(descripcion_limpia) < 10:
        descripcion_limpia = f"Reporte generado por IA: {texto_final}"

    nuevo_reporte = {
        "espacio_id": espacio_id_vinculado,
        "espacio_nombre": nombre_aula_final,
        "descripcion": descripcion_limpia,
        "gravedad": gravedad,
        "fecha_reporte": obtener_hora_ecuador(),
        "estado": "abierto",
        "usuario_id": usuario_id,
        "docente_nombre": nombre_usuario,
        "origen": "ia_audio" if file else "ia_texto",
        "texto_original": texto_final,
    }

    resultado = await coleccion_reportes.insert_one(nuevo_reporte)

    return {
        "status": "success",
        "accion": "REPORTE",
        "db_registro_id": str(resultado.inserted_id),
        "origen_peticion": texto_final,
        "aula_identificada": nombre_aula_final,
        "espacio_id_asociado": espacio_id_vinculado,
        "respuesta_app": f"Listo, registré el reporte para {nombre_aula_final}.",
    }


async def resolver_reporte_directo(
    texto_final: str,
    usuario_id: str,
    rol_usuario: str,
    nombre_usuario: str,
    file: Optional[UploadFile],
) -> Optional[dict]:
    if not detectar_reporte_directo(texto_final):
        return None

    if rol_usuario == "estudiante":
        return {
            "status": "error",
            "accion": "REPORTE",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": None,
            "espacio_id_asociado": None,
            "respuesta_app": (
                "Como estudiante, puedes consultar información, pero los reportes "
                "de daños deben ser realizados por un docente o administrador."
            ),
        }

    if normalizar_rol(rol_usuario) not in ROLES_CON_ACCIONES:
        return {
            "status": "error",
            "accion": "REPORTE",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": None,
            "espacio_id_asociado": None,
            "respuesta_app": "Tu rol no tiene permisos para generar reportes de incidencias.",
        }

    espacio_id_vinculado = None
    nombre_aula_final = None

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
        nombre_aula_detectado = extraer_nombre_aula_simple(texto_final)

        if not nombre_aula_detectado:
            nombre_aula_detectado = await extraer_aula_con_ia_cacheado(texto_final)

        aula_db = await buscar_aula_por_nombre(nombre_aula_detectado)

        if aula_db:
            espacio_id_vinculado = str(aula_db["_id"])
            nombre_aula_final = aula_db.get("nombre", "Aula identificada")

    if not espacio_id_vinculado:
        return {
            "status": "requiere_informacion",
            "accion": "REPORTE",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": None,
            "espacio_id_asociado": None,
            "respuesta_app": (
                "Detecté que quieres reportar una incidencia, pero no identifiqué el aula. "
                "Indícame el nombre del aula o laboratorio para generar el ticket."
            ),
        }

    texto_norm = normalizar_texto(texto_final)
    gravedad = "media"

    if any(p in texto_norm for p in ["riesgo", "peligro", "humo", "chispa", "corto", "electrico"]):
        gravedad = "alta"
    elif any(p in texto_norm for p in ["menor", "pequeno", "leve"]):
        gravedad = "baja"

    return await crear_reporte(
        texto_final=texto_final,
        usuario_id=usuario_id,
        nombre_usuario=nombre_usuario,
        espacio_id_vinculado=espacio_id_vinculado,
        nombre_aula_final=nombre_aula_final,
        gravedad=gravedad,
        file=file,
    )


async def resolver_reporte_con_ia(
    texto_final: str,
    usuario_id: str,
    rol_usuario: str,
    nombre_usuario: str,
    file: Optional[UploadFile],
    data_ia: dict,
) -> dict:
    gravedad = (data_ia.get("gravedad") or "baja").lower()

    if gravedad not in ["baja", "media", "alta"]:
        gravedad = "baja"

    if rol_usuario == "estudiante":
        return {
            "status": "error",
            "accion": "REPORTE",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": None,
            "espacio_id_asociado": None,
            "respuesta_app": (
                "Como estudiante, puedes consultar información, pero los reportes "
                "de daños deben ser realizados por un docente o administrador."
            ),
        }

    if normalizar_rol(rol_usuario) not in ROLES_CON_ACCIONES:
        return {
            "status": "error",
            "accion": "REPORTE",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": None,
            "espacio_id_asociado": None,
            "respuesta_app": "Tu rol no tiene permisos para generar reportes de incidencias.",
        }

    espacio_id_vinculado = None
    nombre_aula_final = None

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
            "accion": "REPORTE",
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

    return await crear_reporte(
        texto_final=descripcion_limpia.strip(),
        usuario_id=usuario_id,
        nombre_usuario=nombre_usuario,
        espacio_id_vinculado=espacio_id_vinculado,
        nombre_aula_final=nombre_aula_final,
        gravedad=gravedad,
        file=file,
    )


async def resolver_consulta_con_ia(texto_final: str, data_ia: dict) -> dict:
    nombre_aula_detectado = data_ia.get("nombre_aula")
    aula_db = await buscar_aula_por_nombre(nombre_aula_detectado)

    if not aula_db:
        return {
            "status": "requiere_informacion",
            "accion": "CONSULTA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": nombre_aula_detectado,
            "espacio_id_asociado": None,
            "respuesta_app": (
                "No pude identificar con seguridad el aula o laboratorio. "
                "Indícame el nombre completo, por ejemplo: Laboratorio de Computación 3."
            ),
        }

    espacio_id = str(aula_db["_id"])
    nombre_aula = aula_db.get("nombre", "Aula identificada")

    horarios = await buscar_horarios_de_aula(espacio_id)

    if not horarios:
        return {
            "status": "success",
            "accion": "CONSULTA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": nombre_aula,
            "espacio_id_asociado": espacio_id,
            "horarios": [],
            "respuesta_app": (
                f"Encontré el {nombre_aula}. "
                "No tiene reservas próximas registradas por el momento."
            ),
            "detalle_aula": {
                "nombre": nombre_aula,
                "bloque": aula_db.get("bloque"),
                "tipo": aula_db.get("tipo"),
                "estado_actual": aula_db.get("estado_actual"),
            },
        }

    respuesta = f"Encontré estos horarios próximos para {nombre_aula}:\n\n"

    for index, reserva in enumerate(horarios, start=1):
        respuesta += f"{index}. {formatear_horario_reserva(reserva)}\n"

    return {
        "status": "success",
        "accion": "CONSULTA",
        "db_registro_id": None,
        "origen_peticion": texto_final,
        "aula_identificada": nombre_aula,
        "espacio_id_asociado": espacio_id,
        "horarios": [convertir_reserva_simple(reserva) for reserva in horarios],
        "respuesta_app": respuesta.strip(),
        "detalle_aula": {
            "nombre": nombre_aula,
            "bloque": aula_db.get("bloque"),
            "tipo": aula_db.get("tipo"),
            "estado_actual": aula_db.get("estado_actual"),
        },
    }

async def resolver_liberacion_aula(
    texto_final: str,
    usuario_id: str,
    rol_usuario: str,
    nombre_usuario: str,
) -> Optional[dict]:
    if not detectar_solicitud_liberacion_aula(texto_final):
        return None

    if normalizar_rol(rol_usuario) not in ROLES_CON_ACCIONES:
        return {
            "status": "error",
            "accion": "LIBERAR_AULA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": None,
            "espacio_id_asociado": None,
            "respuesta_app": "Tu rol no tiene permisos para liberar aulas.",
        }

    ahora = obtener_hora_ecuador()

    nombre_aula_detectado = extraer_nombre_aula_simple(texto_final)
    aula_db = None
    reserva_activa = None

    # Caso 1: el usuario menciona el aula
    if nombre_aula_detectado:
        aula_db = await buscar_aula_por_nombre(nombre_aula_detectado)

        if not aula_db:
            return {
                "status": "requiere_informacion",
                "accion": "LIBERAR_AULA",
                "db_registro_id": None,
                "origen_peticion": texto_final,
                "aula_identificada": nombre_aula_detectado,
                "espacio_id_asociado": None,
                "respuesta_app": (
                    f"No pude encontrar el aula '{nombre_aula_detectado}'. "
                    "Verifica el nombre o intenta con algo como: Laboratorio de Computación 3A."
                ),
            }

        espacio_id = str(aula_db["_id"])

        filtro_reserva = {
            "espacio_id": espacio_id,
            "hora_inicio": {"$lte": ahora},
            "hora_fin": {"$gte": ahora},
        }

        # Si es docente, solo puede liberar su propia reserva.
        # Si es admin o ayudante, puede liberar cualquier reserva activa.
        if normalizar_rol(rol_usuario) == "docente":
            filtro_reserva["usuario_id"] = usuario_id

        reserva_activa = await coleccion_reservas.find_one(filtro_reserva)

    # Caso 2: el usuario no menciona aula, se usa su clase activa
    if not reserva_activa:
        reserva_activa = await buscar_clase_activa_docente(usuario_id)

        if reserva_activa:
            espacio_id = reserva_activa.get("espacio_id")

            try:
                aula_db = await coleccion_espacios.find_one(
                    {"_id": obtener_object_id(espacio_id)}
                )
            except HTTPException:
                aula_db = None

    if not reserva_activa:
        return {
            "status": "requiere_informacion",
            "accion": "LIBERAR_AULA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": nombre_aula_detectado,
            "espacio_id_asociado": None,
            "respuesta_app": (
                "No encontré una reserva activa para liberar. "
                "Si quieres liberar un aula específica, indícame el nombre completo."
            ),
        }

    espacio_id = reserva_activa.get("espacio_id")
    nombre_aula = "el aula"

    if aula_db:
        nombre_aula = aula_db.get("nombre", "el aula")

    # Cierra la reserva activa en la hora actual
    await coleccion_reservas.update_one(
        {"_id": reserva_activa["_id"]},
        {
            "$set": {
                "hora_fin": ahora,
                "estado": "liberada",
                "fecha_liberacion": ahora,
                "liberado_por": usuario_id,
                "liberado_por_nombre": nombre_usuario,
            }
        },
    )

    # Cambia el estado del aula a disponible
    try:
        await coleccion_espacios.update_one(
            {"_id": obtener_object_id(espacio_id)},
            {
                "$set": {
                    "estado_actual": "disponible",
                    "fecha_actualizacion_estado": ahora,
                }
            },
        )
    except HTTPException:
        pass

    return {
        "status": "success",
        "accion": "LIBERAR_AULA",
        "db_registro_id": str(reserva_activa["_id"]),
        "origen_peticion": texto_final,
        "aula_identificada": nombre_aula,
        "espacio_id_asociado": espacio_id,
        "respuesta_app": (
            f"Listo, liberé {nombre_aula}. "
            f"La reserva quedó cerrada a las {ahora.strftime('%H:%M')}."
        ),
        "reserva_liberada": {
            "id": str(reserva_activa["_id"]),
            "espacio_id": espacio_id,
            "espacio_nombre": nombre_aula,
            "hora_liberacion": ahora.strftime("%Y-%m-%d %H:%M"),
            "liberado_por": nombre_usuario,
        },
    }

async def resolver_solicitud_reserva(
    texto_final: str,
    usuario_id: str,
    rol_usuario: str,
    nombre_usuario: str,
) -> Optional[dict]:
    if not detectar_solicitud_reserva(texto_final):
        return None

    if normalizar_rol(rol_usuario) not in ROLES_CON_ACCIONES:
        return {
            "status": "error",
            "accion": "RESERVA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": None,
            "espacio_id_asociado": None,
            "respuesta_app": "Tu rol no tiene permisos para crear reservas.",
        }

    nombre_aula_detectado = extraer_nombre_aula_simple(texto_final)

    if not nombre_aula_detectado:
        nombre_aula_detectado = await extraer_aula_con_ia_cacheado(texto_final)

    if not nombre_aula_detectado:
        return {
            "status": "requiere_informacion",
            "accion": "RESERVA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": None,
            "espacio_id_asociado": None,
            "respuesta_app": (
                "Entendí que quieres hacer una reserva, pero no identifiqué el aula. "
                "Indícame el nombre del aula o laboratorio."
            ),
        }

    aula_db = await buscar_aula_por_nombre(nombre_aula_detectado)

    if not aula_db:
        return {
            "status": "requiere_informacion",
            "accion": "RESERVA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": nombre_aula_detectado,
            "espacio_id_asociado": None,
            "respuesta_app": (
                f"No encontré el aula '{nombre_aula_detectado}'. "
                "Verifica el nombre, por ejemplo: Laboratorio de Computación 3 - A."
            ),
        }

    rango = extraer_rango_horario(texto_final)

    if not rango:
        reserva_pendiente_incompleta = {
            "espacio_id": str(aula_db["_id"]),
            "espacio_nombre": aula_db.get("nombre"),
            "materia": extraer_materia_reserva(texto_final),
            "hora_inicio": None,
            "hora_fin": None,
            "usuario_id": usuario_id,
            "docente_nombre": nombre_usuario,
            "incompleta": True,
        }

        guardar_reserva_pendiente(usuario_id, reserva_pendiente_incompleta)

        return {
            "status": "requiere_horario",
            "accion": "RESERVA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": aula_db.get("nombre"),
            "espacio_id_asociado": str(aula_db["_id"]),
            "respuesta_app": (
                f"Identifiqué el {aula_db.get('nombre')}. "
                "Ahora indícame el horario, por ejemplo: de 1 pm a 3 pm."
            ),
            "reserva_pendiente": {
                "espacio_id": str(aula_db["_id"]),
                "espacio_nombre": aula_db.get("nombre"),
                "materia": reserva_pendiente_incompleta["materia"],
                "hora_inicio": None,
                "hora_fin": None,
                "incompleta": True,
            },
        }

    hora_inicio_num, hora_fin_num = rango

    ahora = obtener_hora_ecuador()
    fecha_reserva = ahora.date()

    hora_inicio = datetime(
        fecha_reserva.year,
        fecha_reserva.month,
        fecha_reserva.day,
        hora_inicio_num,
        0,
        0,
    )

    hora_fin = datetime(
        fecha_reserva.year,
        fecha_reserva.month,
        fecha_reserva.day,
        hora_fin_num,
        0,
        0,
    )

    espacio_id = str(aula_db["_id"])
    nombre_aula = aula_db.get("nombre", "Aula identificada")

    conflicto = await verificar_conflicto_reserva(
        espacio_id=espacio_id,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
    )

    if conflicto:
        return {
            "status": "error",
            "accion": "RESERVA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": nombre_aula,
            "espacio_id_asociado": espacio_id,
            "respuesta_app": (
                f"El {nombre_aula} no está disponible de "
                f"{hora_inicio.strftime('%H:%M')} a {hora_fin.strftime('%H:%M')}. "
                "Ya existe una reserva en ese horario."
            ),
        }

    materia = extraer_materia_reserva(texto_final)

    reserva_pendiente = {
        "espacio_id": espacio_id,
        "espacio_nombre": nombre_aula,
        "materia": materia,
        "hora_inicio": hora_inicio,
        "hora_fin": hora_fin,
        "usuario_id": usuario_id,
        "docente_nombre": nombre_usuario,
        "incompleta": False,
    }

    guardar_reserva_pendiente(usuario_id, reserva_pendiente)

    return {
        "status": "pendiente_confirmacion",
        "accion": "RESERVA",
        "db_registro_id": None,
        "origen_peticion": texto_final,
        "aula_identificada": nombre_aula,
        "espacio_id_asociado": espacio_id,
        "respuesta_app": (
            f"El {nombre_aula} está disponible hoy de "
            f"{hora_inicio.strftime('%H:%M')} a {hora_fin.strftime('%H:%M')}. "
            "¿Confirmas la reserva?"
        ),
        "reserva_pendiente": {
            "espacio_id": espacio_id,
            "espacio_nombre": nombre_aula,
            "materia": materia,
            "hora_inicio": hora_inicio.strftime("%Y-%m-%d %H:%M"),
            "hora_fin": hora_fin.strftime("%Y-%m-%d %H:%M"),
            "incompleta": False,
        },
    }


async def resolver_horario_para_reserva_pendiente(
    texto_final: str,
    usuario_id: str,
) -> Optional[dict]:
    pendiente = obtener_reserva_pendiente(usuario_id)

    if not pendiente:
        return None

    if not pendiente.get("incompleta"):
        return None

    rango = extraer_rango_horario(texto_final)

    if not rango:
        return None

    hora_inicio_num, hora_fin_num = rango

    ahora = obtener_hora_ecuador()
    fecha_reserva = ahora.date()

    hora_inicio = datetime(
        fecha_reserva.year,
        fecha_reserva.month,
        fecha_reserva.day,
        hora_inicio_num,
        0,
        0,
    )

    hora_fin = datetime(
        fecha_reserva.year,
        fecha_reserva.month,
        fecha_reserva.day,
        hora_fin_num,
        0,
        0,
    )

    conflicto = await verificar_conflicto_reserva(
        espacio_id=pendiente["espacio_id"],
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
    )

    if conflicto:
        eliminar_reserva_pendiente(usuario_id)

        return {
            "status": "error",
            "accion": "RESERVA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": pendiente.get("espacio_nombre"),
            "espacio_id_asociado": pendiente.get("espacio_id"),
            "respuesta_app": (
                f"El {pendiente.get('espacio_nombre')} no está disponible de "
                f"{hora_inicio.strftime('%H:%M')} a {hora_fin.strftime('%H:%M')}. "
                "Ya existe una reserva en ese horario."
            ),
        }

    pendiente["hora_inicio"] = hora_inicio
    pendiente["hora_fin"] = hora_fin
    pendiente["incompleta"] = False

    guardar_reserva_pendiente(usuario_id, pendiente)

    return {
        "status": "pendiente_confirmacion",
        "accion": "RESERVA",
        "db_registro_id": None,
        "origen_peticion": texto_final,
        "aula_identificada": pendiente.get("espacio_nombre"),
        "espacio_id_asociado": pendiente.get("espacio_id"),
        "respuesta_app": (
            f"El {pendiente.get('espacio_nombre')} está disponible hoy de "
            f"{hora_inicio.strftime('%H:%M')} a {hora_fin.strftime('%H:%M')}. "
            "¿Confirmas la reserva?"
        ),
        "reserva_pendiente": {
            "espacio_id": pendiente.get("espacio_id"),
            "espacio_nombre": pendiente.get("espacio_nombre"),
            "materia": pendiente.get("materia"),
            "hora_inicio": hora_inicio.strftime("%Y-%m-%d %H:%M"),
            "hora_fin": hora_fin.strftime("%Y-%m-%d %H:%M"),
            "incompleta": False,
        },
    }


async def resolver_confirmacion_reserva(
    texto_final: str,
    usuario_id: str,
) -> Optional[dict]:
    pendiente = obtener_reserva_pendiente(usuario_id)

    if not pendiente:
        return None

    if detectar_cancelacion_reserva(texto_final):
        eliminar_reserva_pendiente(usuario_id)

        return {
            "status": "cancelada",
            "accion": "RESERVA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": pendiente.get("espacio_nombre"),
            "espacio_id_asociado": pendiente.get("espacio_id"),
            "respuesta_app": "Listo, cancelé la reserva pendiente.",
        }

    if not detectar_confirmacion_reserva(texto_final):
        return None

    if pendiente.get("incompleta"):
        return {
            "status": "requiere_horario",
            "accion": "RESERVA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": pendiente.get("espacio_nombre"),
            "espacio_id_asociado": pendiente.get("espacio_id"),
            "respuesta_app": (
                f"Aún falta el horario para reservar el {pendiente.get('espacio_nombre')}. "
                "Indícame algo como: de 1 pm a 3 pm."
            ),
        }

    espacio_id = pendiente["espacio_id"]
    hora_inicio = pendiente["hora_inicio"]
    hora_fin = pendiente["hora_fin"]

    conflicto = await verificar_conflicto_reserva(
        espacio_id=espacio_id,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
    )

    if conflicto:
        eliminar_reserva_pendiente(usuario_id)

        return {
            "status": "error",
            "accion": "RESERVA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": pendiente.get("espacio_nombre"),
            "espacio_id_asociado": espacio_id,
            "respuesta_app": (
                f"Ya no se pudo reservar el {pendiente.get('espacio_nombre')}. "
                "Alguien ocupó ese horario antes de confirmar."
            ),
        }

    nueva_reserva = {
        "espacio_id": espacio_id,
        "materia": pendiente.get("materia", "Reserva generada por asistente IA"),
        "hora_inicio": hora_inicio,
        "hora_fin": hora_fin,
        "usuario_id": pendiente.get("usuario_id"),
        "docente_nombre": pendiente.get("docente_nombre"),
        "estado": "activa",
        "origen": "ia_chat",
        "fecha_creacion": obtener_hora_ecuador(),
    }

    resultado = await coleccion_reservas.insert_one(nueva_reserva)
    eliminar_reserva_pendiente(usuario_id)

    return {
        "status": "success",
        "accion": "RESERVA",
        "db_registro_id": str(resultado.inserted_id),
        "origen_peticion": texto_final,
        "aula_identificada": pendiente.get("espacio_nombre"),
        "espacio_id_asociado": espacio_id,
        "respuesta_app": (
            f"Listo, reservé el {pendiente.get('espacio_nombre')} para hoy de "
            f"{hora_inicio.strftime('%H:%M')} a {hora_fin.strftime('%H:%M')}."
        ),
        "reserva": {
            "id": str(resultado.inserted_id),
            "espacio_id": espacio_id,
            "espacio_nombre": pendiente.get("espacio_nombre"),
            "materia": nueva_reserva["materia"],
            "hora_inicio": hora_inicio.strftime("%Y-%m-%d %H:%M"),
            "hora_fin": hora_fin.strftime("%Y-%m-%d %H:%M"),
        },
    }


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

    limpiar_caches_si_corresponde()

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
    print("TEXTO FINAL IA:", texto_final)
    print("ES RESERVA:", detectar_solicitud_reserva(texto_final))

    respuesta_confirmacion_reserva = await resolver_confirmacion_reserva(
        texto_final=texto_final,
        usuario_id=usuario_id,
    )

    if respuesta_confirmacion_reserva:
        print("CONFIRMACION RESERVA SIN GPT")
        return respuesta_confirmacion_reserva

    respuesta_horario_reserva_pendiente = await resolver_horario_para_reserva_pendiente(
        texto_final=texto_final,
        usuario_id=usuario_id,
    )

    if respuesta_horario_reserva_pendiente:
        print("HORARIO PARA RESERVA PENDIENTE SIN GPT")
        return respuesta_horario_reserva_pendiente

    respuesta_liberacion_aula = await resolver_liberacion_aula(
        texto_final=texto_final,
        usuario_id=usuario_id,
        rol_usuario=rol_usuario,
        nombre_usuario=nombre_usuario,
    )

    if respuesta_liberacion_aula:
        print("LIBERACION AULA SIN GPT")
        return respuesta_liberacion_aula

    respuesta_solicitud_reserva = await resolver_solicitud_reserva(
        texto_final=texto_final,
        usuario_id=usuario_id,
        rol_usuario=rol_usuario,
        nombre_usuario=nombre_usuario,
    )

    if respuesta_solicitud_reserva:
        print("SOLICITUD RESERVA SIN GPT")
        return respuesta_solicitud_reserva

    respuesta_disponibilidad_horario = await resolver_disponibilidad_por_horario(texto_final)

    if respuesta_disponibilidad_horario:
        print("DISPONIBILIDAD POR HORARIO SIN GPT")
        return respuesta_disponibilidad_horario

    respuesta_general_espacios = await resolver_consulta_espacios_general(texto_final)

    if respuesta_general_espacios:
        print("CONSULTA GENERAL SIN GPT")
        return respuesta_general_espacios

    respuesta_directa_reporte = await resolver_reporte_directo(
        texto_final=texto_final,
        usuario_id=usuario_id,
        rol_usuario=rol_usuario,
        nombre_usuario=nombre_usuario,
        file=file,
    )

    if respuesta_directa_reporte:
        print("REPORTE DIRECTO SIN GPT")
        return respuesta_directa_reporte

    respuesta_disponibilidad_aula = await resolver_disponibilidad_aula_especifica(texto_final)

    if respuesta_disponibilidad_aula:
        print("DISPONIBILIDAD AULA ESPECIFICA SIN GPT")
        return respuesta_disponibilidad_aula

    respuesta_directa_consulta = await resolver_consulta_directa(texto_final)

    if respuesta_directa_consulta:
        print("CONSULTA DIRECTA SIN GPT")
        return respuesta_directa_consulta

    print("USANDO IA SOLO COMO RESPALDO")
    data_ia = await analizar_solicitud_con_ia_cacheado(texto_final, rol_usuario)

    accion = data_ia.get("accion")

    if accion == "REPORTE":
        return await resolver_reporte_con_ia(
            texto_final=texto_final,
            usuario_id=usuario_id,
            rol_usuario=rol_usuario,
            nombre_usuario=nombre_usuario,
            file=file,
            data_ia=data_ia,
        )

    if accion == "CONSULTA":
        return await resolver_consulta_con_ia(texto_final, data_ia)

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