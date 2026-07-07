from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from datetime import datetime
from typing import Optional, List
from app.database import db

# 🔒 Importamos tu función de seguridad JWT
from app.usuarios.utils import obtener_usuario_actual  

router = APIRouter(prefix="/ia", tags=["IA & Procesamiento"])

@router.post("/procesar-solicitud", status_code=status.HTTP_201_CREATED)
async def procesar_solicitud_axis(
    file: Optional[UploadFile] = File(None),
    texto_chat: Optional[str] = Form(None),
    # 🔒 Inyección de seguridad: Valida el token JWT antes de entrar a la lógica
    usuario_actual: dict = Depends(obtener_usuario_actual)  
):
    # 1. Extraer los datos del usuario autenticado desde el payload del JWT
    usuario_id = usuario_actual.get("id") or str(usuario_actual.get("_id"))
    rol_usuario = usuario_actual.get("rol", "").lower()
    nombre_usuario = usuario_actual.get("nombre_completo")
    
    if not file and not texto_chat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes proporcionar al menos un archivo de audio o un texto de chat."
        )
    
    # ------------------------------------------------------------------
    # [AQUÍ VA TU CÓDIGO ACTUAL: Transcripción con Whisper si viene 'file']
    # [Y TU LLAMADA A GPT PARA OBTENER 'accion', 'descripcion_limpia', etc.]
    # ------------------------------------------------------------------
    # NOTA: Asegúrate de guardar el JSON parseado de GPT en una variable (ej: data_ia)
    # Ejemplo simulado del retorno de tu GPT:
    # accion = data_ia.get("accion") -> "REPORTE" o "CONSULTA"
    
    documento_creado_id = None
    espacio_id_vinculado = None
    nombre_aula_final = "No especificado"

    # --- 3. LÓGICA DE NEGOCIO POR ROLES Y AUTOMATIZACIÓN DE HORARIOS ---
# --- 3. LÓGICA DE NEGOCIO POR ROLES Y AUTOMATIZACIÓN DE HORARIOS ---
    if accion == "REPORTE":
        
        # ❌ RESTRICCIÓN: Estudiantes no crean reportes
        if rol_usuario == "estudiante":
            return {
                "status": "error",
                "respuesta_app": "Como estudiante de la UCE, solo puedes consultar horarios. Los reportes de daños deben ser realizados por un docente o ayudante."
            }
            
        # 👨‍🏫 VALIDACIÓN PARA DOCENTES Y AYUDANTES
        elif rol_usuario in ["profesor", "ayudante", "docente"]:
            hora_actual_iso = datetime.utcnow().isoformat()
            
            # Paso 1: Intentar buscar clase activa por horario
            clase_activa = await db.reservas.find_one({
                "docente_id": usuario_id,
                "hora_inicio": {"$lte": hora_actual_iso},
                "hora_fin": {"$gte": hora_actual_iso}
            })
            
            if clase_activa:
                espacio_id_vinculado = clase_activa.get("espacio_id")
                aula_db = await db.espacios.find_one({"_id": db.ObjectId(espacio_id_vinculado)})
                nombre_aula_final = aula_db.get("nombre") if aula_db else "Aula Horario"
            else:
                # Paso 2: Si no hay reserva, intentar buscar el aula en el texto analizado por GPT
                nombre_aula_detectado = data_ia.get("nombre_aula")
                
                if nombre_aula_detectado:
                    aula_db = await db.espacios.find_one({
                        "nombre": {"$regex": f"^{nombre_aula_detectado}$", "$options": "i"}
                    })
                    if aula_db:
                        espacio_id_vinculado = str(aula_db.get("_id"))
                        nombre_aula_final = aula_db.get("nombre")

            # 🛑 CRÍTICO: Si fallaron ambos métodos (No hay reserva Y no mencionó el aula)
            if not espacio_id_vinculado:
                return {
                    "status": "requiere_informacion",
                    "db_registro_id": None,
                    "aula_identificada": None,
                    "espacio_id_asociado": None,
                    # Le pedimos el dato directamente al usuario sin guardar nada
                    "respuesta_app": "Estimado docente, no identifiqué una reserva activa en este horario ni el aula en su mensaje. Por favor, indíqueme en qué aula o laboratorio se encuentra el problema para generar el ticket."
                }

        # Guardamos el reporte SOLAMENTE si pasó los filtros anteriores y el aula está identificada
        nuevo_reporte = {
            "espacio_id": espacio_id_vinculado,  
            "descripcion": data_ia.get("descripcion_limpia"),
            "gravedad": (data_ia.get("gravedad") or "baja").lower(),
            "fecha_reporte": datetime.utcnow().isoformat(),
            "estado": "abierto",
            "reportado_por": usuario_id  
        }
        
        resultado = await db.reportes.insert_one(nuevo_reporte)
        documento_creado_id = str(resultado.inserted_id)
    # Respuesta unificada lista para pintar en la interfaz de React Native
    return {
        "status": "success",
        "db_registro_id": documento_creado_id,
        "origen_peticion": texto_chat,
        "aula_identificada": nombre_aula_final,
        "espacio_id_asociado": espacio_id_vinculado,
        "respuesta_app": data_ia.get("respuesta_natural")
    }