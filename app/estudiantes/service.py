from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import UploadFile
from bson import ObjectId
from bson.errors import InvalidId

from app.database import db
from app.estudiantes.schemas import ClaseEstudianteData, EdificioData


coleccion_edificios = db["edificios"]
coleccion_grupos = db["grupos"]
coleccion_horarios = db["horarios_estudiantes"]
coleccion_asignaciones = db["estudiante_grupos"]
coleccion_espacios = db["espacios"]
coleccion_reportes = db["reportes"]

UPLOADS_REPORTES_DIR = Path("uploads/reportes")
UPLOADS_REPORTES_DIR.mkdir(parents=True, exist_ok=True)
MAX_IMAGENES_REPORTE = 3
MAX_IMAGEN_MB = 6
TIPOS_IMAGEN_VALIDOS = {"image/jpeg", "image/png", "image/webp"}


DIAS_SEMANA = {
    0: "lunes",
    1: "martes",
    2: "miercoles",
    3: "jueves",
    4: "viernes",
    5: "sabado",
    6: "domingo",
}


DIAS_ALIAS = {
    "miércoles": "miercoles",
    "miercoles": "miercoles",
    "sábado": "sabado",
    "sabado": "sabado",
}


def obtener_hora_ecuador() -> datetime:
    return datetime.utcnow() - timedelta(hours=5)


def obtener_usuario_id(usuario_actual: dict) -> str:
    return str(
        usuario_actual.get("id")
        or usuario_actual.get("user_id")
        or usuario_actual.get("sub")
        or ""
    ).strip()


def obtener_email(usuario_actual: dict) -> Optional[str]:
    email = usuario_actual.get("email")
    return str(email).strip().lower() if email else None


def normalizar_dia(dia: str) -> str:
    dia = str(dia or "").strip().lower()
    return DIAS_ALIAS.get(dia, dia)


def obtener_dia_actual() -> str:
    return DIAS_SEMANA[obtener_hora_ecuador().weekday()]


def hora_a_minutos(hora: str) -> int:
    partes = str(hora or "00:00").split(":")
    h = int(partes[0]) if partes and partes[0] else 0
    m = int(partes[1]) if len(partes) > 1 and partes[1] else 0
    return h * 60 + m


def obtener_minutos_actuales() -> int:
    ahora = obtener_hora_ecuador()
    return ahora.hour * 60 + ahora.minute


def calcular_estado_clase(hora_inicio: str, hora_fin: str) -> str:
    minutos_actuales = obtener_minutos_actuales()
    inicio = hora_a_minutos(hora_inicio)
    fin = hora_a_minutos(hora_fin)

    if inicio <= minutos_actuales <= fin:
        return "actual"

    if minutos_actuales < inicio:
        return "proxima"

    return "finalizada"


def object_id_or_none(valor: str):
    try:
        return ObjectId(str(valor))
    except (InvalidId, TypeError):
        return None


async def obtener_asignacion_activa(usuario_actual: dict) -> Optional[dict]:
    usuario_id = obtener_usuario_id(usuario_actual)
    email = obtener_email(usuario_actual)

    filtros = []

    if usuario_id:
        filtros.append({"usuario_id": usuario_id, "activo": True})

    if email:
        filtros.append({"email": email, "activo": True})

    if not filtros:
        return None

    asignacion = await coleccion_asignaciones.find_one({"$or": filtros})

    if asignacion:
        return asignacion

    # MVP académico: si el estudiante todavía no fue asignado manualmente,
    # se lo vincula una sola vez al grupo base creado por seed.py.
    # Esto mantiene el horario en MongoDB y evita datos quemados en el frontend.
    grupo_default = await coleccion_grupos.find_one({"id": "grupo-sexto-a", "activo": {"$ne": False}})

    if not grupo_default:
        return None

    documento = {
        "usuario_id": usuario_id,
        "email": email,
        "grupo_id": str(grupo_default.get("id") or grupo_default.get("_id")),
        "grupo_nombre": grupo_default.get("nombre"),
        "activo": True,
        "asignado_por": "auto_mvp",
        "fecha_asignacion": obtener_hora_ecuador(),
    }

    await coleccion_asignaciones.insert_one(documento)

    return documento


async def obtener_grupo_asignado(usuario_actual: dict) -> Optional[dict]:
    asignacion = await obtener_asignacion_activa(usuario_actual)

    if not asignacion:
        return None

    grupo_id = asignacion.get("grupo_id")
    grupo_object_id = object_id_or_none(grupo_id)

    if grupo_object_id:
        grupo = await coleccion_grupos.find_one({"_id": grupo_object_id})
        if grupo:
            return grupo

    return await coleccion_grupos.find_one({"id": grupo_id})


async def obtener_edificio(edificio_id) -> Optional[EdificioData]:
    edificio = None
    edificio_object_id = object_id_or_none(edificio_id)

    if edificio_object_id:
        edificio = await coleccion_edificios.find_one({"_id": edificio_object_id})

    if edificio is None:
        edificio = await coleccion_edificios.find_one({"id": str(edificio_id)})

    if not edificio:
        return None

    return EdificioData(
        id=str(edificio.get("_id") or edificio.get("id")),
        nombre=edificio.get("nombre", "Edificio"),
        bloque=edificio.get("bloque"),
        referencia=edificio.get("referencia"),
        latitude=float(edificio.get("latitude", edificio.get("latitud", 0))),
        longitude=float(edificio.get("longitude", edificio.get("longitud", 0))),
    )


async def construir_clase(raw: dict, grupo: dict) -> Optional[ClaseEstudianteData]:
    edificio = await obtener_edificio(raw.get("edificio_id"))

    if edificio is None:
        return None

    grupo_nombre = grupo.get("nombre") or grupo.get("codigo") or "Grupo asignado"

    return ClaseEstudianteData(
        id=str(raw.get("_id") or raw.get("id")),
        materia=raw.get("materia", "Materia sin nombre"),
        docente=raw.get("docente", "Docente no registrado"),
        grupo=grupo_nombre,
        aula=raw.get("aula", raw.get("espacio_nombre", "Aula no registrada")),
        edificio=edificio,
        dia_semana=normalizar_dia(raw.get("dia_semana")),
        hora_inicio=raw.get("hora_inicio", "00:00"),
        hora_fin=raw.get("hora_fin", "00:00"),
        estado=calcular_estado_clase(
            raw.get("hora_inicio", "00:00"),
            raw.get("hora_fin", "00:00"),
        ),
    )


async def get_mis_clases_hoy(usuario_actual: dict) -> List[ClaseEstudianteData]:
    grupo = await obtener_grupo_asignado(usuario_actual)

    if not grupo:
        return []

    dia_actual = obtener_dia_actual()

    # IMPORTANTE:
    # Los horarios usan el id lógico del grupo, por ejemplo: "grupo-sexto-a"
    # No usan el _id de Mongo.
    grupo_id = str(grupo.get("id") or grupo.get("_id"))

    clases = []
    cursor = coleccion_horarios.find(
        {
            "grupo_id": grupo_id,
            "dia_semana": dia_actual,
            "activo": {"$ne": False},
        }
    ).sort("hora_inicio", 1)

    async for item in cursor:
        clase = await construir_clase(item, grupo)
        if clase is not None:
            clases.append(clase)

    clases.sort(key=lambda item: hora_a_minutos(item.hora_inicio))
    return clases

async def get_clase_actual(usuario_actual: dict) -> Optional[ClaseEstudianteData]:
    clases_hoy = await get_mis_clases_hoy(usuario_actual)

    for clase in clases_hoy:
        if clase.estado == "actual":
            return clase

    return None


async def get_clase_por_id(usuario_actual: dict, clase_id: str) -> Optional[ClaseEstudianteData]:
    clases_hoy = await get_mis_clases_hoy(usuario_actual)

    for clase in clases_hoy:
        if clase.id == clase_id:
            return clase

    return None


async def get_proxima_clase(usuario_actual: dict) -> Optional[ClaseEstudianteData]:
    clases_hoy = await get_mis_clases_hoy(usuario_actual)

    candidatas = [clase for clase in clases_hoy if clase.estado in ("actual", "proxima")]

    if not candidatas:
        return None

    candidatas.sort(key=lambda item: hora_a_minutos(item.hora_inicio))
    return candidatas[0]


async def buscar_espacio_por_nombre_aula(nombre_aula: str) -> Optional[dict]:
    if not nombre_aula:
        return None

    return await coleccion_espacios.find_one(
        {"nombre": {"$regex": f"^{nombre_aula}$", "$options": "i"}}
    )


async def guardar_imagenes_reporte(imagenes: Optional[List[UploadFile]]) -> list[dict]:
    archivos_guardados = []

    if not imagenes:
        return archivos_guardados

    if len(imagenes) > MAX_IMAGENES_REPORTE:
        raise ValueError(f"Solo puedes adjuntar hasta {MAX_IMAGENES_REPORTE} imágenes.")

    for imagen in imagenes:
        if not imagen or not imagen.filename:
            continue

        content_type = imagen.content_type or ""

        if content_type not in TIPOS_IMAGEN_VALIDOS:
            raise ValueError("Solo se permiten imágenes JPG, PNG o WEBP.")

        contenido = await imagen.read()

        if len(contenido) > MAX_IMAGEN_MB * 1024 * 1024:
            raise ValueError(f"Cada imagen debe pesar máximo {MAX_IMAGEN_MB} MB.")

        extension = Path(imagen.filename).suffix.lower()
        if extension not in [".jpg", ".jpeg", ".png", ".webp"]:
            extension = ".jpg"

        filename = f"{uuid4().hex}{extension}"
        ruta = UPLOADS_REPORTES_DIR / filename
        ruta.write_bytes(contenido)

        archivos_guardados.append({
            "nombre_original": imagen.filename,
            "filename": filename,
            "url": f"/uploads/reportes/{filename}",
            "content_type": content_type,
        })

    return archivos_guardados


async def crear_reporte_clase_actual_estudiante(
    descripcion: str,
    gravedad: str,
    usuario_actual: dict,
    imagenes: Optional[List[UploadFile]] = None,
) -> dict:
    clase = await get_clase_actual(usuario_actual)

    if clase is None:
        raise ValueError(
            "No tienes una clase activa en este momento. Solo puedes reportar incidencias durante tu clase actual."
        )

    if gravedad not in ["baja", "media", "alta"]:
        gravedad = "media"

    espacio_db = await buscar_espacio_por_nombre_aula(clase.aula)
    espacio_id = str(espacio_db["_id"]) if espacio_db else clase.id
    espacio_nombre = espacio_db.get("nombre") if espacio_db else clase.aula
    espacio_bloque = espacio_db.get("bloque") if espacio_db else clase.edificio.bloque
    imagenes_guardadas = await guardar_imagenes_reporte(imagenes)

    total = await coleccion_reportes.count_documents({})

    usuario_id = obtener_usuario_id(usuario_actual) or "estudiante"
    estudiante_nombre = usuario_actual.get("nombre") or usuario_actual.get("email") or "Estudiante"

    nuevo_reporte = {
        "codigo": f"TK-{total + 1:03d}",
        "espacio_id": espacio_id,
        "espacio_nombre": espacio_nombre,
        "espacio_bloque": espacio_bloque,
        "clase_id": clase.id,
        "materia": clase.materia,
        "descripcion": descripcion.strip(),
        "gravedad": gravedad,
        "recurso_afectado": "General",
        "fecha_reporte": obtener_hora_ecuador(),
        "estado": "abierto",
        "usuario_id": usuario_id,
        "email": obtener_email(usuario_actual),
        "estudiante_email": obtener_email(usuario_actual),
        "estudiante_nombre": estudiante_nombre,
        "tipo_usuario": "estudiante",
        "origen": "estudiante_app",
        "imagenes": imagenes_guardadas,
        "adjuntos": imagenes_guardadas,
    }

    resultado = await coleccion_reportes.insert_one(nuevo_reporte)

    return {
        "id": str(resultado.inserted_id),
        "codigo": nuevo_reporte["codigo"],
        "materia": clase.materia,
        "aula": clase.aula,
        "edificio": clase.edificio,
        "descripcion": nuevo_reporte["descripcion"],
        "gravedad": gravedad,
        "estado": "abierto",
        "imagenes": imagenes_guardadas,
    }


async def asignar_grupo_estudiante(payload, usuario_actual: dict) -> dict:
    grupo_id = payload.grupo_id
    grupo_object_id = object_id_or_none(grupo_id)

    grupo = None
    if grupo_object_id:
        grupo = await coleccion_grupos.find_one({"_id": grupo_object_id})

    if grupo is None:
        grupo = await coleccion_grupos.find_one({"id": grupo_id})

    if not grupo:
        raise ValueError("No se encontró el grupo indicado.")

    usuario_id = str(payload.usuario_id or "").strip() or None
    email = str(payload.email or "").strip().lower() or None

    if not usuario_id and not email:
        raise ValueError("Debes enviar usuario_id o email del estudiante.")

    filtro = {}
    if usuario_id:
        filtro["usuario_id"] = usuario_id
    if email:
        filtro["email"] = email

    await coleccion_asignaciones.update_many(filtro, {"$set": {"activo": False}})

    documento = {
        **filtro,
        "grupo_id": str(grupo.get("id") or grupo.get("_id")),
        "grupo_nombre": grupo.get("nombre"),
        "activo": True,
        "asignado_por": usuario_actual.get("email") or usuario_actual.get("nombre"),
        "fecha_asignacion": obtener_hora_ecuador(),
    }

    resultado = await coleccion_asignaciones.insert_one(documento)
    documento["id"] = str(resultado.inserted_id)
    documento.pop("_id", None)

    return documento


def serializar_fecha(valor) -> str | None:
    if valor is None:
        return None
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return str(valor)


async def get_mis_reportes_estudiante(usuario_actual: dict) -> list[dict]:
    usuario_id = obtener_usuario_id(usuario_actual)
    email = obtener_email(usuario_actual)

    filtros = []

    if usuario_id:
        filtros.append({"usuario_id": usuario_id})

    if email:
        filtros.append({"email": email})
        filtros.append({"estudiante_email": email})

    if not filtros:
        return []

    reportes = []
    cursor = coleccion_reportes.find({"$or": filtros}).sort("fecha_reporte", -1)

    async for item in cursor:
        reportes.append({
            "id": str(item.get("_id")),
            "codigo": item.get("codigo", "TK-000"),
            "materia": item.get("materia"),
            "aula": item.get("aula") or item.get("espacio_nombre"),
            "espacio_nombre": item.get("espacio_nombre"),
            "descripcion": item.get("descripcion", "Sin descripción"),
            "gravedad": item.get("gravedad", "media"),
            "estado": item.get("estado", "abierto"),
            "fecha_reporte": serializar_fecha(item.get("fecha_reporte")),
            "imagenes": item.get("imagenes") or item.get("adjuntos") or [],
        })

    return reportes
