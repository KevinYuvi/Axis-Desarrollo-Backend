from fastapi import UploadFile
from typing import Optional

from app.ia.state import limpiar_caches_si_corresponde
from app.ia.audio_service import transcribir_audio
from app.ia.reservas_service import (
    resolver_confirmacion_reserva,
    resolver_horario_para_reserva_pendiente,
    resolver_solicitud_reserva,
)
from app.ia.liberacion_service import resolver_liberacion_aula
from app.ia.reportes_service import resolver_reporte_directo, resolver_reporte_con_ia
from app.ia.consultas_service import (
    resolver_disponibilidad_por_horario,
    resolver_consulta_espacios_general,
    resolver_disponibilidad_aula_especifica,
    resolver_consulta_directa,
    resolver_consulta_con_ia,
)
from app.ia.classifier_service import analizar_solicitud_con_ia_cacheado


def obtener_usuario_id(usuario_actual: dict) -> str:
    usuario_id = (
        usuario_actual.get("_id")
        or usuario_actual.get("id")
        or usuario_actual.get("sub")
        or usuario_actual.get("user_id")
    )

    if not usuario_id:
        raise ValueError("No se pudo determinar el ID del usuario desde el token")

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


async def procesar_solicitud_axis_service(
    file: Optional[UploadFile],
    texto_chat: Optional[str],
    usuario_actual: dict,
):
    usuario_id = obtener_usuario_id(usuario_actual)
    rol_usuario = obtener_rol_usuario(usuario_actual)
    nombre_usuario = obtener_nombre_usuario(usuario_actual)

    limpiar_caches_si_corresponde()

    texto_final = ""

    if texto_chat and texto_chat.strip():
        texto_final = texto_chat.strip()

    if file:
        texto_transcrito = await transcribir_audio(file)

        if texto_final:
            texto_final = f"{texto_final}\n\nTranscripción del audio: {texto_transcrito}"
        else:
            texto_final = texto_transcrito

    print("TEXTO FINAL IA:", texto_final)

    respuesta_confirmacion = await resolver_confirmacion_reserva(
        texto_final=texto_final,
        usuario_id=usuario_id,
    )

    if respuesta_confirmacion:
        print("CONFIRMACION RESERVA")
        return respuesta_confirmacion

    respuesta_horario_pendiente = await resolver_horario_para_reserva_pendiente(
        texto_final=texto_final,
        usuario_id=usuario_id,
    )

    if respuesta_horario_pendiente:
        print("HORARIO PARA RESERVA PENDIENTE")
        return respuesta_horario_pendiente

    respuesta_liberacion = await resolver_liberacion_aula(
        texto_final=texto_final,
        usuario_id=usuario_id,
        rol_usuario=rol_usuario,
        nombre_usuario=nombre_usuario,
    )

    if respuesta_liberacion:
        print("LIBERACION AULA")
        return respuesta_liberacion

    respuesta_reserva = await resolver_solicitud_reserva(
        texto_final=texto_final,
        usuario_id=usuario_id,
        rol_usuario=rol_usuario,
        nombre_usuario=nombre_usuario,
    )

    if respuesta_reserva:
        print("SOLICITUD RESERVA")
        return respuesta_reserva

    respuesta_reporte = await resolver_reporte_directo(
        texto_final=texto_final,
        usuario_id=usuario_id,
        rol_usuario=rol_usuario,
        nombre_usuario=nombre_usuario,
        file=file,
    )

    if respuesta_reporte:
        print("REPORTE DIRECTO")
        return respuesta_reporte

    respuesta_disponibilidad_horario = await resolver_disponibilidad_por_horario(texto_final)

    if respuesta_disponibilidad_horario:
        print("DISPONIBILIDAD POR HORARIO")
        return respuesta_disponibilidad_horario

    respuesta_general_espacios = await resolver_consulta_espacios_general(texto_final)

    if respuesta_general_espacios:
        print("CONSULTA GENERAL ESPACIOS")
        return respuesta_general_espacios

    respuesta_disponibilidad_aula = await resolver_disponibilidad_aula_especifica(texto_final)

    if respuesta_disponibilidad_aula:
        print("DISPONIBILIDAD AULA ESPECIFICA")
        return respuesta_disponibilidad_aula

    respuesta_consulta_directa = await resolver_consulta_directa(texto_final)

    if respuesta_consulta_directa:
        print("CONSULTA DIRECTA")
        return respuesta_consulta_directa

    print("USANDO IA COMO RESPALDO")
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
        return await resolver_consulta_con_ia(
            texto_final=texto_final,
            data_ia=data_ia,
        )

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