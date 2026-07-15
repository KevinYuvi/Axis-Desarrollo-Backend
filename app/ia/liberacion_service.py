import re

from app.database import db
from app.usuarios.utils import normalizar_rol
from app.ia.text_utils import (
    normalizar_texto,
    extraer_nombre_aula_simple,
    obtener_hora_ecuador,
)
from app.ia.aulas_service import (
    buscar_aula_por_nombre,
    buscar_aula_por_id,
    buscar_clase_activa_docente,
    obtener_object_id,
)


coleccion_reservas = db["reservas"]
coleccion_espacios = db["espacios"]

ROLES_CON_ACCIONES = {"docente", "admin", "ayudante"}


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
        r"\bya termine la clase\b",
        r"\btermine la clase\b",
        r"\bfinalice la clase\b",
        r"\bsali del aula\b",
        r"\bsali del laboratorio\b",
    ]

    return any(re.search(patron, texto_norm) for patron in patrones_liberacion)


async def resolver_liberacion_aula(
    texto_final: str,
    usuario_id: str,
    rol_usuario: str,
    nombre_usuario: str,
) -> dict | None:
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
            "estado": {"$nin": ["liberada", "cancelada", "finalizada"]},
            "liberada_anticipadamente": {"$ne": True},
        }

        if normalizar_rol(rol_usuario) == "docente":
            filtro_reserva["usuario_id"] = usuario_id

        reserva_activa = await coleccion_reservas.find_one(filtro_reserva)

    if not reserva_activa:
        reserva_activa = await buscar_clase_activa_docente(usuario_id)

        if reserva_activa:
            espacio_id = reserva_activa.get("espacio_id")
            aula_db = await buscar_aula_por_id(espacio_id)

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

    await coleccion_reservas.update_one(
        {"_id": reserva_activa["_id"]},
        {
            "$set": {
                "hora_fin": ahora,
                "estado": "liberada",
                "fecha_liberacion": ahora,
                "liberado_por": usuario_id,
                "liberado_por_nombre": nombre_usuario,
                "liberada_anticipadamente": True,
            }
        },
    )

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
    except Exception:
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