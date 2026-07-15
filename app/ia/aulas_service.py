import re
from datetime import datetime
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.database import db
from app.ia.text_utils import (
    compactar_texto,
    limpiar_regex,
    normalizar_texto,
    normalizar_numeros_texto,
    obtener_hora_ecuador,
)


coleccion_espacios = db["espacios"]
coleccion_reservas = db["reservas"]


def obtener_object_id(id_valor: str) -> ObjectId:
    try:
        return ObjectId(id_valor)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id enviado no tiene un formato válido de MongoDB",
        )


def generar_variantes_nombre_aula(nombre_aula: str) -> list[str]:
    if not nombre_aula:
        return []

    nombre = normalizar_numeros_texto(nombre_aula)

    variantes = set()

    variantes.add(nombre)

    variantes.add(nombre.replace("laboratorio", "lab"))
    variantes.add(nombre.replace("lab", "laboratorio"))
    variantes.add(nombre.replace("computacion", "comp"))

    variantes.add(nombre.replace(" 1 a", " 1a"))
    variantes.add(nombre.replace(" 2 a", " 2a"))
    variantes.add(nombre.replace(" 3 a", " 3a"))
    variantes.add(nombre.replace(" 4 a", " 4a"))
    variantes.add(nombre.replace(" 5 a", " 5a"))
    variantes.add(nombre.replace(" 5 d", " 5d"))

    variantes.add(nombre.replace(" 1a", " 1 a"))
    variantes.add(nombre.replace(" 2a", " 2 a"))
    variantes.add(nombre.replace(" 3a", " 3 a"))
    variantes.add(nombre.replace(" 4a", " 4 a"))
    variantes.add(nombre.replace(" 5a", " 5 a"))
    variantes.add(nombre.replace(" 5d", " 5 d"))

    # Caso importante:
    # Whisper puede convertir "Aula 5 desde..." en "Aula 5 d".
    # Si no existe Aula 5D, luego se buscará Aula 5.
    match_aula_letra = re.search(
        r"\b(aula|salon|sala|lab|laboratorio)\s+(\d+)\s+[a-z]\b",
        nombre,
    )

    if match_aula_letra:
        variantes.add(f"{match_aula_letra.group(1)} {match_aula_letra.group(2)}")

    match_aula_letra_compacta = re.search(
        r"\b(aula|salon|sala|lab|laboratorio)\s+(\d+)([a-z])\b",
        nombre,
    )

    if match_aula_letra_compacta:
        tipo = match_aula_letra_compacta.group(1)
        numero = match_aula_letra_compacta.group(2)
        letra = match_aula_letra_compacta.group(3)

        variantes.add(f"{tipo} {numero}")
        variantes.add(f"{tipo} {numero} {letra}")

    return list({v.strip() for v in variantes if v.strip()})


async def buscar_aula_por_nombre(nombre_aula: Optional[str]) -> Optional[dict]:
    if not nombre_aula:
        return None

    variantes = generar_variantes_nombre_aula(nombre_aula)

    # 1. Coincidencia exacta por nombre
    patrones_exactos = [
        f"^{limpiar_regex(variante)}$"
        for variante in variantes
        if variante
    ]

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

    # 2. Coincidencia compactada exacta: "Aula 5" == "aula5"
    nombre_buscado_compacto = compactar_texto(nombre_aula)

    if nombre_buscado_compacto:
        cursor = coleccion_espacios.find({}, {"_id": 1, "nombre": 1})

        async for espacio in cursor:
            nombre_db_compacto = compactar_texto(espacio.get("nombre", ""))

            if nombre_db_compacto == nombre_buscado_compacto:
                return await coleccion_espacios.find_one({"_id": espacio["_id"]})

    # 3. Fallback sin letra final: "Aula 5D" → "Aula 5"
    for variante in variantes:
        variante_norm = normalizar_texto(variante)

        match = re.search(
            r"\b(aula|salon|sala|lab|laboratorio)\s+(\d+)\s*[a-z]\b",
            variante_norm,
        )

        if not match:
            continue

        base = f"{match.group(1)} {match.group(2)}"

        aula = await coleccion_espacios.find_one(
            {
                "nombre": {
                    "$regex": f"^{limpiar_regex(base)}$",
                    "$options": "i",
                }
            }
        )

        if aula:
            return aula

    # 4. Búsqueda parcial controlada
    palabras = [
        palabra
        for palabra in normalizar_texto(nombre_aula).split()
        if palabra not in {
            "el",
            "la",
            "de",
            "del",
            "en",
            "aula",
            "laboratorio",
            "lab",
            "salon",
            "sala",
            "quiero",
            "reserva",
            "reservar",
            "desde",
            "hasta",
            "pm",
            "am",
        }
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

    return None


async def buscar_aula_por_id(espacio_id: str) -> Optional[dict]:
    try:
        object_id = obtener_object_id(espacio_id)
    except HTTPException:
        return None

    return await coleccion_espacios.find_one({"_id": object_id})


async def buscar_clase_activa_docente(usuario_id: str) -> Optional[dict]:
    ahora = obtener_hora_ecuador()

    reserva = await coleccion_reservas.find_one(
        {
            "usuario_id": usuario_id,
            "hora_inicio": {"$lte": ahora},
            "hora_fin": {"$gte": ahora},
            "estado": {"$nin": ["liberada", "cancelada", "finalizada"]},
            "liberada_anticipadamente": {"$ne": True},
        }
    )

    return reserva


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
            "estado": {"$nin": ["liberada", "cancelada", "finalizada"]},
            "liberada_anticipadamente": {"$ne": True},
        }
    )

    return reserva_en_conflicto


async def verificar_disponibilidad_actual_aula(espacio_id: str) -> tuple[bool, Optional[dict]]:
    ahora = obtener_hora_ecuador()

    reserva_activa = await coleccion_reservas.find_one(
        {
            "espacio_id": espacio_id,
            "hora_inicio": {"$lte": ahora},
            "hora_fin": {"$gte": ahora},
            "estado": {"$nin": ["liberada", "cancelada", "finalizada"]},
            "liberada_anticipadamente": {"$ne": True},
        }
    )

    return reserva_activa is None, reserva_activa


async def buscar_horarios_de_aula(espacio_id: str, limite: int = 5) -> list[dict]:
    ahora = obtener_hora_ecuador()

    cursor = coleccion_reservas.find(
        {
            "espacio_id": espacio_id,
            "hora_fin": {"$gte": ahora},
            "estado": {"$nin": ["liberada", "cancelada", "finalizada"]},
            "liberada_anticipadamente": {"$ne": True},
        }
    ).sort("hora_inicio", 1).limit(limite)

    horarios = []

    async for reserva in cursor:
        horarios.append(reserva)

    return horarios


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