import os
import json
from datetime import datetime
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from openai import OpenAI
from app.database import db  # Conexión configurada a MongoDB

router = APIRouter(prefix="/ia", tags=["Inteligencia Artificial"])

# Inicialización segura de OpenAI API Key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key and os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("OPENAI_API_KEY"):
                api_key = line.split("=")[1].strip().strip('"').strip("'")

client = OpenAI(api_key=api_key)

@router.post("/procesar-solicitud", status_code=status.HTTP_201_CREATED)
async def procesar_solicitud_axis(
    file: Optional[UploadFile] = File(None),
    texto_chat: Optional[str] = Form(None)
):
    """
    Endpoint híbrido de AXIS (Audio/Chat): Mapea intenciones basándose en colecciones 
    normalizadas de MongoDB vinculando dinámicamente el espacio_id.
    """
    if not file and not texto_chat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes proporcionar al menos un archivo de audio o un texto de chat."
        )
    
    texto_a_procesar = ""
    transcripcion_realizada = False
    
    try:
        # --- 1. CAPTURA DE ENTRADA (AUDIO O CHAT) ---
        if file:
            if not file.content_type.startswith("audio/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El archivo enviado no cuenta con un formato de audio válido."
                )
            transcription = client.audio.transcriptions.create(
                model="whisper-1", 
                file=(file.filename, file.file, file.content_type),
                language="es"
            )
            texto_a_procesar = transcription.text
            transcripcion_realizada = True
        else:
            texto_a_procesar = texto_chat

        if not texto_a_procesar or not texto_a_procesar.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La solicitud proporcionada está vacía o el audio no contiene voz legible."
            )

        # --- 2. EXTRACCIÓN SEMÁNTICA CON GPT-4O-MINI ---
        prompt_sistema = (
            "Eres el motor de IA de AXIS, plataforma de gestión de la Universidad Central del Ecuador (UCE).\n"
            "Analiza el texto de origen y genera un objeto JSON estrictamente formateado con los siguientes campos:\n"
            "{\n"
            "  \"accion\": \"RESERVA\" | \"REPORTE\" | \"OTRO\",\n"
            "  \"nombre_aula\": string (Nombre limpio del aula o laboratorio detectado, ej: 'Laboratorio de Computación 3'),\n"
            "  \"descripcion_limpia\": string (Resumen detallado y formal del incidente detectado),\n"
            "  \"gravedad\": \"alta\" | \"media\" | \"baja\" (En minúsculas),\n"
            "  \"respuesta_natural\": string (Confirmación empática y profesional para el usuario final)\n"
            "}"
        )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0.1,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Texto de origen: {texto_a_procesar}"}
            ]
        )
        
        data_ia = json.loads(completion.choices[0].message.content)
        accion = data_ia.get("accion")
        nombre_aula_detectado = data_ia.get("nombre_aula")
        
        documento_creado_id = None
        espacio_id_vinculado = None

        # --- 3. CRUCE DINÁMICO DE DATOS E INSERCIÓN EN MONGO ---
# --- 3. CRUCE DINÁMICO DE DATOS E INSERCIÓN EN MONGO ---
        if accion == "REPORTE":
            # Cambiamos db.aulas por db.espacios basado en tus colecciones reales
            aula_db = await db.espacios.find_one({
                "nombre": {"$regex": f"^{nombre_aula_detectado}$", "$options": "i"}
            })
            
            # Búsqueda secundaria por si acaso el nombre no es 100% idéntico
            if not aula_db:
                aula_db = await db.espacios.find_one({
                    "nombre": {"$regex": nombre_aula_detectado, "$options": "i"}
                })
            
            if aula_db:
                # Extraemos el ID dinámico (soporta tanto '_id' nativo de Mongo como 'id' manual si lo guardaste como string)
                espacio_id_vinculado = str(aula_db.get("_id") or aula_db.get("id"))
            else:
                print(f"[AXIS IA WARNING] No se encontró el espacio '{nombre_aula_detectado}' en la colección 'espacios'.")
            
            # Construimos el reporte según tu esquema exacto
            nuevo_reporte = {
                "espacio_id": espacio_id_vinculado,  
                "descripcion": data_ia.get("descripcion_limpia"),
                "gravedad": data_ia.get("gravedad") or "baja",
                "fecha_reporte": datetime.utcnow().isoformat(),
                "estado": "abierto"
            }
            
            # Guardamos el reporte en tu colección 'reportes'
            resultado = await db.reportes.insert_one(nuevo_reporte)
            documento_creado_id = str(resultado.inserted_id)

        # --- 4. RESPUESTA REFORMULADA ---
        return {
            "status": "success",
            "db_registro_id": documento_creado_id,
            "origen_peticion": "audio" if transcripcion_realizada else "chat",
            "aula_identificada": nombre_aula_detectado,
            "espacio_id_asociado": espacio_id_vinculado,
            "respuesta_app": data_ia.get("respuesta_natural")
        }

    except Exception as e:
        print(f"[AXIS IA ERROR] Falla en la integración: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el procesamiento unificado: {str(e)}"
        )