import re
from datetime import datetime, timedelta
from typing import Optional


MAX_CHARS_IA = 500


def obtener_hora_ecuador() -> datetime:
    return datetime.utcnow() - timedelta(hours=5)


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
    texto = re.sub(r"[,.;:!¡¿?]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def normalizar_texto_horario(texto: str) -> str:
    """
    Normaliza texto para detectar horas.
    Importante: aquí NO se elimina ':' hasta después de convertir 10:30.
    """
    texto = str(texto or "").lower().strip()

    texto = texto.replace("á", "a")
    texto = texto.replace("é", "e")
    texto = texto.replace("í", "i")
    texto = texto.replace("ó", "o")
    texto = texto.replace("ú", "u")
    texto = texto.replace("ñ", "n")

    texto = texto.replace("a. m.", "am")
    texto = texto.replace("p. m.", "pm")
    texto = texto.replace("a.m.", "am")
    texto = texto.replace("p.m.", "pm")
    texto = texto.replace("a.m", "am")
    texto = texto.replace("p.m", "pm")
    texto = texto.replace("a m", "am")
    texto = texto.replace("p m", "pm")

    texto = texto.replace("hasta las", "hasta")
    texto = texto.replace("hasta la", "hasta")
    texto = texto.replace("desde las", "desde")
    texto = texto.replace("desde la", "desde")
    texto = texto.replace("de las", "de")
    texto = texto.replace("de la", "de")

    texto = texto.replace("-", " ")
    texto = texto.replace("_", " ")

    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def detectar_fecha_reserva(texto: str):
    texto_norm = normalizar_texto(texto)
    ahora = obtener_hora_ecuador()

    if "pasado manana" in texto_norm:
        return ahora.date() + timedelta(days=2), "pasado mañana"

    if "manana" in texto_norm:
        return ahora.date() + timedelta(days=1), "mañana"

    if "hoy" in texto_norm:
        return ahora.date(), "hoy"

    # Regla principal para AXIS:
    # Si el usuario no especifica día, se entiende que la reserva es para HOY.
    return ahora.date(), "hoy"


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


def normalizar_numeros_texto(texto: str) -> str:
    texto = f" {normalizar_texto(texto)} "

    reemplazos = {
        " cero ": " 0 ",
        " una ": " 1 ",
        " uno ": " 1 ",
        " dos ": " 2 ",
        " tres ": " 3 ",
        " cuatro ": " 4 ",
        " cinco ": " 5 ",
        " seis ": " 6 ",
        " siete ": " 7 ",
        " ocho ": " 8 ",
        " nueve ": " 9 ",
        " diez ": " 10 ",
        " once ": " 11 ",
        " doce ": " 12 ",
        " trece ": " 13 ",
        " catorce ": " 14 ",
        " quince ": " 15 ",
        " dieciseis ": " 16 ",
        " diecisiete ": " 17 ",
        " dieciocho ": " 18 ",
        " diecinueve ": " 19 ",
        " veinte ": " 20 ",
        " treinta ": " 30 ",
        " cuarenta ": " 40 ",
        " cincuenta ": " 50 ",
    }

    for palabra, numero in reemplazos.items():
        texto = texto.replace(palabra, numero)

    return re.sub(r"\s+", " ", texto).strip()


def preparar_texto_horario(texto: str) -> str:
    texto_base = normalizar_texto_horario(texto)

    texto_base = re.sub(r"\b(\d{1,2}):(\d{1,2})\s*(am|pm)?\b", r"\1 y \2 \3", texto_base)
    texto_base = re.sub(r"\b(\d{1,2})y(\d{1,2})\b", r"\1 y \2", texto_base)

    texto_base = re.sub(r"\b(\d{1,2})\s*(pa|pe|p)\b", r"\1 pm", texto_base)
    texto_base = re.sub(r"\b(\d{1,2})\s*(eme|m)\b", r"\1 am", texto_base)

    texto_base = texto_base.replace(",", " ")
    texto_base = texto_base.replace(".", " ")
    texto_base = texto_base.replace(";", " ")
    texto_base = texto_base.replace(":", " ")
    texto_base = texto_base.replace("!", " ")
    texto_base = texto_base.replace("?", " ")

    texto_base = re.sub(r"\s+", " ", texto_base).strip()

    texto_numeros = normalizar_numeros_texto(texto_base)

    texto_numeros = texto_numeros.replace("p m", "pm")
    texto_numeros = texto_numeros.replace("a m", "am")

    return re.sub(r"\s+", " ", texto_numeros).strip()


def convertir_hora_a_24(hora_texto: str, periodo: Optional[str]) -> Optional[int]:
    try:
        hora = int(hora_texto)

        if hora < 0 or hora > 23:
            return None

        if periodo:
            periodo = periodo.lower().replace(".", "").strip()

            if periodo == "pm" and hora < 12:
                hora += 12

            if periodo == "am" and hora == 12:
                hora = 0

        return hora

    except Exception:
        return None


def normalizar_minuto(minuto_texto: Optional[str]) -> int:
    if not minuto_texto:
        return 0

    try:
        minuto = int(minuto_texto)

        if minuto < 0 or minuto > 59:
            return 0

        return minuto

    except Exception:
        return 0


def extraer_rango_horario(texto: str) -> Optional[tuple[int, int, int, int]]:
    texto_norm = preparar_texto_horario(texto)

    patrones = [
        r"\bdesde\s+(\d{1,2})(?:\s+y\s+(\d{1,2}))?\s*(am|pm)?\s+hasta\s+(\d{1,2})(?:\s+y\s+(\d{1,2}))?\s*(am|pm)?\b",
        r"\bde\s+(\d{1,2})(?:\s+y\s+(\d{1,2}))?\s*(am|pm)?\s+a\s+(\d{1,2})(?:\s+y\s+(\d{1,2}))?\s*(am|pm)?\b",
        r"\b(\d{1,2})(?:\s+y\s+(\d{1,2}))?\s*(am|pm)?\s+a\s+(\d{1,2})(?:\s+y\s+(\d{1,2}))?\s*(am|pm)?\b",
        r"\b(\d{1,2})(?:\s+y\s+(\d{1,2}))?\s*(am|pm)?\s+hasta\s+(\d{1,2})(?:\s+y\s+(\d{1,2}))?\s*(am|pm)?\b",
    ]

    for patron in patrones:
        match = re.search(patron, texto_norm)

        if not match:
            continue

        hora_inicio_txt = match.group(1)
        minuto_inicio_txt = match.group(2)
        periodo_inicio = match.group(3)

        hora_fin_txt = match.group(4)
        minuto_fin_txt = match.group(5)
        periodo_fin = match.group(6)

        if not periodo_inicio and periodo_fin:
            periodo_inicio = periodo_fin

        if periodo_inicio and not periodo_fin:
            periodo_fin = periodo_inicio

        hora_inicio = convertir_hora_a_24(hora_inicio_txt, periodo_inicio)
        hora_fin = convertir_hora_a_24(hora_fin_txt, periodo_fin)

        minuto_inicio = normalizar_minuto(minuto_inicio_txt)
        minuto_fin = normalizar_minuto(minuto_fin_txt)

        if hora_inicio is None or hora_fin is None:
            continue

        return hora_inicio, minuto_inicio, hora_fin, minuto_fin

    return None


def extraer_fecha_horario_desde_texto(texto: str) -> Optional[dict]:
    rango = extraer_rango_horario(texto)

    if not rango:
        return None

    hora_inicio_num, minuto_inicio_num, hora_fin_num, minuto_fin_num = rango
    fecha_reserva, etiqueta_fecha = detectar_fecha_reserva(texto)

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

    if hora_fin <= hora_inicio:
        hora_fin = hora_fin + timedelta(days=1)

    return {
        "hora_inicio": hora_inicio,
        "hora_fin": hora_fin,
        "etiqueta_fecha": etiqueta_fecha,
    }


def detectar_solicitud_reserva(texto: str) -> bool:
    texto_norm = normalizar_texto(texto)

    patrones_reserva = [
        r"\bquiero reservar\b",
        r"\bquiero una reserva\b",
        r"\bquiero hacer una reserva\b",
        r"\bquiero que me reserves\b",
        r"\bnecesito reservar\b",
        r"\bnecesito una reserva\b",
        r"\bhacer una reserva\b",
        r"\bhaz una reserva\b",
        r"\bgenerar una reserva\b",
        r"\bgenerame una reserva\b",
        r"\bme generes una reserva\b",
        r"\bme puedes reservar\b",
        r"\bpuedes reservar\b",
        r"\bme reservas\b",
        r"\breservame\b",
        r"\breservar\b",
        r"\breserva\b",
        r"\breservalo\b",
        r"\breservala\b",
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
        r"\bocupar el laboratorio\b",
    ]

    hay_reserva = any(re.search(patron, texto_norm) for patron in patrones_reserva)

    if not hay_reserva:
        return False

    patrones_consulta_sin_reserva = [
        r"\bque reservas\b",
        r"\bver reservas\b",
        r"\bmis reservas\b",
        r"\bconsultar reservas\b",
        r"\bmostrar reservas\b",
        r"\blistar reservas\b",
        r"\benlistar reservas\b",
    ]

    if any(re.search(patron, texto_norm) for patron in patrones_consulta_sin_reserva):
        return False

    return True


def detectar_confirmacion(texto: str) -> bool:
    texto_norm = normalizar_texto(texto)

    confirmaciones = {
        "si",
        "sí",
        "confirmo",
        "confirma",
        "confirmar",
        "dale",
        "ok",
        "okay",
        "listo",
        "acepto",
        "hazlo",
        "reservalo",
        "reservala",
        "si confirma",
        "sí confirma",
    }

    if texto_norm in confirmaciones:
        return True

    patrones = [
        r"\bsi confirma\b",
        r"\bconfirmo la reserva\b",
        r"\bconfirmar reserva\b",
        r"\bhaz la reserva\b",
        r"\bcrea la reserva\b",
    ]

    return any(re.search(patron, texto_norm) for patron in patrones)


def detectar_cancelacion(texto: str) -> bool:
    texto_norm = normalizar_texto(texto)

    cancelaciones = {
        "no",
        "cancelar",
        "cancela",
        "cancelalo",
        "cancelala",
        "olvida",
        "mejor no",
        "ya no",
        "no la reserves",
        "no reserves",
    }

    if texto_norm in cancelaciones:
        return True

    patrones = [
        r"\bcancela la reserva\b",
        r"\bcancelar reserva\b",
        r"\bmejor no\b",
        r"\bya no\b",
        r"\bno la reserves\b",
        r"\bno reserves\b",
    ]

    return any(re.search(patron, texto_norm) for patron in patrones)


def detectar_reporte_directo(texto: str) -> bool:
    texto_norm = normalizar_texto(texto)

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

    return any(palabra in texto_norm for palabra in palabras_reporte)


def detectar_consulta_directa(texto: str) -> bool:
    texto_norm = normalizar_texto(texto)

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

    return any(palabra in texto_norm for palabra in palabras_consulta)


def extraer_nombre_aula_simple(texto: str) -> Optional[str]:
    texto_norm = normalizar_numeros_texto(texto)

    patrones = [
        r"\blaboratorio\s+de\s+computacion\s+\d+\s*[a-z]\b",
        r"\blaboratorio\s+de\s+computacion\s+\d+\b",
        r"\blaboratorio\s+\d+\s*[a-z]\b",
        r"\blaboratorio\s+\d+\b",
        r"\blab\s+\d+\s*[a-z]\b",
        r"\blab\s+\d+\b",
        r"\baula\s+\d+\s*[a-z]\b",
        r"\baula\s+\d+\b",
        r"\bsalon\s+\d+\s*[a-z]\b",
        r"\bsalon\s+\d+\b",
        r"\bsala\s+\d+\s*[a-z]\b",
        r"\bsala\s+\d+\b",
    ]

    for patron in patrones:
        match = re.search(patron, texto_norm)

        if match:
            return match.group(0).strip()

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

        if not match:
            continue

        materia = match.group(1).strip()

        materia = re.sub(
            r"\s+de\s+\d{1,2}(?:\s+y\s+\d{1,2})?\s*(am|pm)?\s+a\s+\d{1,2}(?:\s+y\s+\d{1,2})?\s*(am|pm)?",
            "",
            materia,
        ).strip()

        materia = re.sub(
            r"\s+desde\s+\d{1,2}(?:\s+y\s+\d{1,2})?\s*(am|pm)?\s+hasta\s+\d{1,2}(?:\s+y\s+\d{1,2})?\s*(am|pm)?",
            "",
            materia,
        ).strip()

        if len(materia) >= 3:
            return materia.capitalize()

    return "Reserva generada por asistente IA"