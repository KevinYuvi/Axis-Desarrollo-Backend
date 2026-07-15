from datetime import datetime, timedelta

from app.database import db
from app.usuarios.utils import normalizar_rol
from app.ia.state import (
    guardar_reserva_pendiente,
    obtener_reserva_pendiente,
    eliminar_reserva_pendiente,
)
from app.ia.text_utils import (
    detectar_solicitud_reserva,
    detectar_confirmacion,
    detectar_cancelacion,
    extraer_nombre_aula_simple,
    extraer_rango_horario,
    extraer_materia_reserva,
    obtener_hora_ecuador,
    detectar_fecha_reserva,
    normalizar_texto,
)
from app.ia.aulas_service import (
    buscar_aula_por_nombre,
    verificar_conflicto_reserva,
)


coleccion_reservas = db["reservas"]

ROLES_CON_ACCIONES = {"docente", "admin", "ayudante"}


def construir_fechas_reserva(
    hora_inicio_num: int,
    minuto_inicio_num: int,
    hora_fin_num: int,
    minuto_fin_num: int,
    texto_final: str = "",
) -> tuple[datetime, datetime, str]:
    ahora = obtener_hora_ecuador()
    fecha_reserva, etiqueta_fecha = detectar_fecha_reserva(texto_final)

    hora_inicio = datetime(
        fecha_reserva.year,
        fecha_reserva.month,
        fecha_reserva.day,
        hora_inicio_num,
        minuto_inicio_num,
        0,
    )

    hora_fin = datetime(
        fecha_reserva.year,
        fecha_reserva.month,
        fecha_reserva.day,
        hora_fin_num,
        minuto_fin_num,
        0,
    )

    texto_norm = normalizar_texto(texto_final)
    usuario_dijo_hoy = "hoy" in texto_norm
    usuario_dijo_manana = "manana" in texto_norm or "pasado manana" in texto_norm

    if hora_inicio <= ahora and not usuario_dijo_hoy and not usuario_dijo_manana:
        hora_inicio = hora_inicio + timedelta(days=1)
        hora_fin = hora_fin + timedelta(days=1)
        etiqueta_fecha = "mañana"

    return hora_inicio, hora_fin, etiqueta_fecha


async def resolver_solicitud_reserva(
    texto_final: str,
    usuario_id: str,
    rol_usuario: str,
    nombre_usuario: str,
) -> dict | None:
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
        return {
            "status": "requiere_informacion",
            "accion": "RESERVA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": None,
            "espacio_id_asociado": None,
            "respuesta_app": (
                "Entendí que quieres hacer una reserva, pero no identifiqué el aula. "
                "Dime algo como: reservar Aula 5 mañana de 7 am a 9 am."
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
                "Verifica el nombre, por ejemplo: Aula 5 o Laboratorio de Computación 3A."
            ),
        }

    rango = extraer_rango_horario(texto_final)

    if not rango:
        reserva_pendiente = {
            "espacio_id": str(aula_db["_id"]),
            "espacio_nombre": aula_db.get("nombre"),
            "materia": extraer_materia_reserva(texto_final),
            "hora_inicio": None,
            "hora_fin": None,
            "usuario_id": usuario_id,
            "docente_nombre": nombre_usuario,
            "incompleta": True,
            "texto_contexto": texto_final,
        }

        guardar_reserva_pendiente(usuario_id, reserva_pendiente)

        return {
            "status": "requiere_horario",
            "accion": "RESERVA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": aula_db.get("nombre"),
            "espacio_id_asociado": str(aula_db["_id"]),
            "respuesta_app": (
                f"Identifiqué el {aula_db.get('nombre')}. "
                "Ahora dime el horario, por ejemplo: mañana de 7 am a 9 am."
            ),
            "reserva_pendiente": {
                "espacio_id": str(aula_db["_id"]),
                "espacio_nombre": aula_db.get("nombre"),
                "materia": reserva_pendiente["materia"],
                "hora_inicio": None,
                "hora_fin": None,
                "incompleta": True,
            },
        }

    hora_inicio_num, minuto_inicio_num, hora_fin_num, minuto_fin_num = rango

    hora_inicio, hora_fin, etiqueta_fecha = construir_fechas_reserva(
        hora_inicio_num,
        minuto_inicio_num,
        hora_fin_num,
        minuto_fin_num,
        texto_final,
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
                f"El {nombre_aula} no está disponible {etiqueta_fecha} de "
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
        "etiqueta_fecha": etiqueta_fecha,
        "texto_contexto": texto_final,
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
            f"El {nombre_aula} está disponible {etiqueta_fecha} de "
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
            "etiqueta_fecha": etiqueta_fecha,
        },
    }


async def resolver_horario_para_reserva_pendiente(
    texto_final: str,
    usuario_id: str,
) -> dict | None:
    pendiente = obtener_reserva_pendiente(usuario_id)

    if not pendiente:
        return None

    if not pendiente.get("incompleta"):
        return None

    rango = extraer_rango_horario(texto_final)

    if not rango:
        return {
            "status": "requiere_horario",
            "accion": "RESERVA",
            "db_registro_id": None,
            "origen_peticion": texto_final,
            "aula_identificada": pendiente.get("espacio_nombre"),
            "espacio_id_asociado": pendiente.get("espacio_id"),
            "respuesta_app": (
                f"Sigo teniendo pendiente el {pendiente.get('espacio_nombre')}. "
                "Solo falta el horario. Escríbelo así: mañana de 7 am a 9 am."
            ),
            "reserva_pendiente": {
                "espacio_id": pendiente.get("espacio_id"),
                "espacio_nombre": pendiente.get("espacio_nombre"),
                "materia": pendiente.get("materia"),
                "hora_inicio": None,
                "hora_fin": None,
                "incompleta": True,
            },
        }

    hora_inicio_num, minuto_inicio_num, hora_fin_num, minuto_fin_num = rango

    texto_contexto = f"{pendiente.get('texto_contexto', '')} {texto_final}".strip()

    hora_inicio, hora_fin, etiqueta_fecha = construir_fechas_reserva(
        hora_inicio_num,
        minuto_inicio_num,
        hora_fin_num,
        minuto_fin_num,
        texto_contexto,
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
                f"El {pendiente.get('espacio_nombre')} no está disponible {etiqueta_fecha} de "
                f"{hora_inicio.strftime('%H:%M')} a {hora_fin.strftime('%H:%M')}. "
                "Ya existe una reserva en ese horario."
            ),
        }

    pendiente["hora_inicio"] = hora_inicio
    pendiente["hora_fin"] = hora_fin
    pendiente["incompleta"] = False
    pendiente["etiqueta_fecha"] = etiqueta_fecha

    guardar_reserva_pendiente(usuario_id, pendiente)

    return {
        "status": "pendiente_confirmacion",
        "accion": "RESERVA",
        "db_registro_id": None,
        "origen_peticion": texto_final,
        "aula_identificada": pendiente.get("espacio_nombre"),
        "espacio_id_asociado": pendiente.get("espacio_id"),
        "respuesta_app": (
            f"El {pendiente.get('espacio_nombre')} está disponible {etiqueta_fecha} de "
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
            "etiqueta_fecha": etiqueta_fecha,
        },
    }


async def resolver_confirmacion_reserva(
    texto_final: str,
    usuario_id: str,
) -> dict | None:
    pendiente = obtener_reserva_pendiente(usuario_id)

    if not pendiente:
        return None

    if detectar_cancelacion(texto_final):
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

    if not detectar_confirmacion(texto_final):
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
                "Dime algo como: mañana de 7 am a 9 am."
            ),
        }

    espacio_id = pendiente["espacio_id"]
    hora_inicio = pendiente["hora_inicio"]
    hora_fin = pendiente["hora_fin"]
    etiqueta_fecha = pendiente.get("etiqueta_fecha", "")

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
        "liberada_anticipadamente": False,
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
            f"Listo, reservé el {pendiente.get('espacio_nombre')} "
            f"{etiqueta_fecha} de {hora_inicio.strftime('%H:%M')} a {hora_fin.strftime('%H:%M')}."
        ),
        "reserva": {
            "id": str(resultado.inserted_id),
            "espacio_id": espacio_id,
            "espacio_nombre": pendiente.get("espacio_nombre"),
            "materia": nueva_reserva["materia"],
            "hora_inicio": hora_inicio.strftime("%Y-%m-%d %H:%M"),
            "hora_fin": hora_fin.strftime("%Y-%m-%d %H:%M"),
            "etiqueta_fecha": etiqueta_fecha,
        },
    }