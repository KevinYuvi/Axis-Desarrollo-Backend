import re
from datetime import datetime

from app.database import db
from app.ia.text_utils import (
    normalizar_texto,
    extraer_nombre_aula_simple,
    extraer_rango_horario,
    detectar_consulta_directa,
    obtener_hora_ecuador,
)
from app.ia.aulas_service import (
    buscar_aula_por_nombre,
    buscar_horarios_de_aula,
    verificar_disponibilidad_actual_aula,
    verificar_conflicto_reserva,
    convertir_espacio_simple,
    convertir_reserva_simple,
    formatear_horario_reserva,
    formatear_solo_hora,
)


coleccion_espacios = db["espacios"]


def detectar_consulta_espacios_general(texto: str) -> bool:
    texto_norm = normalizar_texto(texto)

    patrones = [
        r"\bcuantas aulas\b",
        r"\bcuantos aulas\b",
        r"\bcuantos laboratorios\b",
        r"\bcuantas salas\b",
        r"\bque aulas\b",
        r"\bcuales aulas\b",
        r"\baulas disponibles\b",
        r"\blaboratorios disponibles\b",
        r"\bespacios disponibles\b",
        r"\baulas hay\b",
        r"\blaboratorios hay\b",
        r"\bcuantos espacios\b",
        r"\bcuantos salones\b",
        r"\bque laboratorios\b",
        r"\blistar aulas\b",
        r"\blista aulas\b",
        r"\blistame aulas\b",
        r"\benlistar aulas\b",
        r"\benlistame aulas\b",
        r"\benlistes.*aulas\b",
        r"\benlistame.*aulas\b",
        r"\bmuestrame.*aulas\b",
        r"\bmostrar.*aulas\b",
        r"\bdame.*aulas\b",
        r"\blistar laboratorios\b",
        r"\blista laboratorios\b",
        r"\blistame laboratorios\b",
        r"\benlistar laboratorios\b",
        r"\benlistame laboratorios\b",
        r"\benlistes.*laboratorios\b",
        r"\benlistame.*laboratorios\b",
        r"\bmuestrame.*laboratorios\b",
        r"\bmostrar.*laboratorios\b",
        r"\bdame.*laboratorios\b",
        r"\btodas las aulas\b",
        r"\btodos los laboratorios\b",
        r"\baulas o laboratorios\b",
        r"\baulas y laboratorios\b",
        r"\bespacios.*disponibles\b",
        r"\bque.*disponibles.*ahora\b",
        r"\bque.*disponibles.*esta hora\b",
        r"\benlistes.*disponibles\b",
    ]

    return any(re.search(patron, texto_norm) for patron in patrones)


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
    tiene_rango = extraer_rango_horario(texto_norm) is not None

    return tiene_disponibilidad and tiene_rango


def extraer_bloque_o_edificio(texto: str) -> str | None:
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


async def resolver_disponibilidad_aula_especifica(texto_final: str) -> dict | None:
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


async def resolver_disponibilidad_por_horario(texto_final: str) -> dict | None:
    if not detectar_disponibilidad_por_horario(texto_final):
        return None

    rango = extraer_rango_horario(texto_final)

    if not rango:
        return None

    hora_inicio_num, minuto_inicio_num, hora_fin_num, minuto_fin_num = rango

    ahora = obtener_hora_ecuador()
    fecha_consulta = ahora.date()

    inicio = datetime(
        fecha_consulta.year,
        fecha_consulta.month,
        fecha_consulta.day,
        hora_inicio_num,
        minuto_inicio_num,
        0,
    )

    fin = datetime(
        fecha_consulta.year,
        fecha_consulta.month,
        fecha_consulta.day,
        hora_fin_num,
        minuto_fin_num,
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
                f"No encontré aulas disponibles hoy de "
                f"{inicio.strftime('%H:%M')} a {fin.strftime('%H:%M')}."
            ),
            "espacios": [],
        }

    respuesta = (
        f"Encontré {len(disponibles)} aula(s) disponible(s) hoy "
        f"de {inicio.strftime('%H:%M')} a {fin.strftime('%H:%M')}."
    )

    return {
        "status": "success",
        "accion": "CONSULTA",
        "db_registro_id": None,
        "origen_peticion": texto_final,
        "aula_identificada": None,
        "espacio_id_asociado": None,
        "respuesta_app": respuesta,
        "espacios": [convertir_espacio_simple(espacio) for espacio in disponibles],
    }


async def resolver_consulta_espacios_general(texto_final: str) -> dict | None:
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

    cursor = coleccion_espacios.find(filtro).sort("nombre", 1)

    espacios = []

    async for espacio in cursor:
        espacios.append(espacio)

    if not espacios:
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

    pide_disponibles = any(
        palabra in texto_norm
        for palabra in [
            "disponible",
            "disponibles",
            "libre",
            "libres",
            "desocupada",
            "desocupadas",
            "a esta hora",
            "ahora",
        ]
    )

    espacios_resultado = []

    if pide_disponibles:
        for espacio in espacios:
            espacio_id = str(espacio["_id"])
            esta_libre, _ = await verificar_disponibilidad_actual_aula(espacio_id)

            if esta_libre:
                espacios_resultado.append(espacio)
    else:
        espacios_resultado = espacios

    total = len(espacios_resultado)

    if total == 0:
        return {
            "status": "success",
            "accion": "CONSULTA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": None,
            "espacio_id_asociado": None,
            "respuesta_app": (
                "No encontré aulas o laboratorios disponibles en este momento."
                if pide_disponibles
                else "No encontré aulas o laboratorios registrados con esos criterios."
            ),
            "espacios": [],
        }

    if pide_disponibles:
        respuesta = f"Encontré {total} espacio(s) disponible(s) en este momento."
    else:
        respuesta = f"Encontré {total} espacio(s) registrado(s)."

    return {
        "status": "success",
        "accion": "CONSULTA",
        "db_registro_id": None,
        "origen_peticion": texto_final,
        "aula_identificada": None,
        "espacio_id_asociado": None,
        "respuesta_app": respuesta,
        "espacios": [convertir_espacio_simple(espacio) for espacio in espacios_resultado],
    }


async def resolver_consulta_directa(texto_final: str) -> dict | None:
    nombre_aula_detectado = extraer_nombre_aula_simple(texto_final)
    es_consulta = detectar_consulta_directa(texto_final)

    if not es_consulta and not nombre_aula_detectado:
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