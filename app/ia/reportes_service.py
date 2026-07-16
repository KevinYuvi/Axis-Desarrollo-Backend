from typing import Optional

from fastapi import UploadFile

from app.database import db
from app.usuarios.utils import normalizar_rol
from app.ia.text_utils import (
    detectar_reporte_directo,
    extraer_nombre_aula_simple,
    normalizar_texto,
    obtener_hora_ecuador,
)
from app.ia.aulas_service import (
    buscar_aula_por_nombre,
    buscar_aula_por_id,
    buscar_clase_activa_docente,
)


coleccion_reportes = db["reportes"]

ROLES_CON_ACCIONES = {"docente", "admin", "ayudante"}


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

    total = await coleccion_reportes.count_documents({})

    nuevo_reporte = {
        "codigo": f"TK-{total + 1:03d}",
        "espacio_id": espacio_id_vinculado,
        "espacio_nombre": nombre_aula_final,
        "descripcion": descripcion_limpia,
        "gravedad": gravedad,
        "recurso_afectado": "General",
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


def calcular_gravedad_reporte(texto_final: str) -> str:
    texto_norm = normalizar_texto(texto_final)

    if any(
        palabra in texto_norm
        for palabra in [
            "riesgo",
            "peligro",
            "humo",
            "chispa",
            "corto",
            "electrico",
            "electricidad",
            "quemado",
            "emergencia",
        ]
    ):
        return "alta"

    if any(
        palabra in texto_norm
        for palabra in [
            "menor",
            "pequeno",
            "pequeño",
            "leve",
            "detalle",
        ]
    ):
        return "baja"

    return "media"


async def resolver_aula_para_reporte(
    texto_final: str,
    usuario_id: str,
) -> tuple[Optional[str], Optional[str]]:
    clase_activa = await buscar_clase_activa_docente(usuario_id)

    if clase_activa:
        espacio_id = clase_activa.get("espacio_id")
        aula_db = await buscar_aula_por_id(espacio_id)

        if aula_db:
            return str(aula_db["_id"]), aula_db.get("nombre", "Aula asignada por horario")

        return espacio_id, "Aula asignada por horario"

    nombre_aula_detectado = extraer_nombre_aula_simple(texto_final)

    if not nombre_aula_detectado:
        return None, None

    aula_db = await buscar_aula_por_nombre(nombre_aula_detectado)

    if not aula_db:
        return None, None

    return str(aula_db["_id"]), aula_db.get("nombre", "Aula identificada")


async def resolver_reporte_directo(
    texto_final: str,
    usuario_id: str,
    rol_usuario: str,
    nombre_usuario: str,
    file: Optional[UploadFile],
) -> dict | None:
    if not detectar_reporte_directo(texto_final):
        return None

    if normalizar_rol(rol_usuario) == "estudiante":
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

    espacio_id_vinculado, nombre_aula_final = await resolver_aula_para_reporte(
        texto_final=texto_final,
        usuario_id=usuario_id,
    )

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

    gravedad = calcular_gravedad_reporte(texto_final)

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
    if normalizar_rol(rol_usuario) == "estudiante":
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

    espacio_id_vinculado, nombre_aula_final = await resolver_aula_para_reporte(
        texto_final=texto_final,
        usuario_id=usuario_id,
    )

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
            "aula_identificada": data_ia.get("nombre_aula"),
            "espacio_id_asociado": None,
            "respuesta_app": (
                "No identifiqué una reserva activa ni el aula en tu mensaje. "
                "Indícame el nombre del aula o laboratorio para generar el ticket."
            ),
        }

    gravedad = (data_ia.get("gravedad") or calcular_gravedad_reporte(texto_final)).lower()

    if gravedad not in ["baja", "media", "alta"]:
        gravedad = "media"

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