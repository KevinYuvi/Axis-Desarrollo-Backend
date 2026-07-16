import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app import occupancy_calculator, scheduler, storage
from app.schemas import AnalyzeRequest, AnalyzeResponse, HealthResponse, LatestAnalysisItem

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lanza el scheduler de análisis automático al iniciar el servicio y lo
    cancela limpiamente al apagarlo.
    """
    scheduler_task = asyncio.create_task(scheduler.run_scheduler_loop())
    yield
    scheduler_task.cancel()


app = FastAPI(
    title="Axis Vision Service",
    description="Microservicio de visión artificial de Axis (análisis automático en segundo plano).",
    version="0.2.0",
    lifespan=lifespan,
)

# Habilitado para desarrollo: el backend principal de Axis puede consultarlo
# desde localhost, Docker o la red local sin bloqueos de CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/vision/health", response_model=HealthResponse)
async def check_vision_service_health():
    """
    Verifica que el vision-service esté en línea.

    @return: estado básico del servicio
    """
    return {"ok": True, "service": "axis-vision-service", "status": "online"}


@app.post("/vision/analyze", response_model=AnalyzeResponse)
async def analyze_occupancy_from_sample(request: AnalyzeRequest):
    """
    Analiza un espacio puntual a partir de una imagen/video local de prueba
    (uso manual/debug — el flujo automático usa el scheduler y
    GET /vision/latest, no este endpoint). Nunca expone detalles internos del
    error (stack trace); ante cualquier fallo inesperado responde 500 controlado.

    @param request: datos del espacio y de la fuente de imagen/video a analizar
    @return: métricas de ocupación calculadas por el vision-service
    """
    try:
        analysis_result = occupancy_calculator.analyze_space(request)
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "message": "No se pudo analizar el espacio con visión artificial"},
        )

    return {
        "ok": True,
        "message": "Análisis de ocupación generado correctamente",
        "data": analysis_result,
    }


@app.get("/vision/latest", response_model=List[LatestAnalysisItem])
async def get_latest_occupancy_analysis():
    """
    Devuelve el último análisis en memoria de cada espacio, generado
    automáticamente por el scheduler cada ANALYSIS_INTERVAL_SECONDS. Antes de
    que el scheduler complete su primer ciclo, la lista puede venir vacía.

    @return: lista de resultados de análisis, uno por espacio ya analizado
    """
    stored_analyses = storage.get_all_analysis()
    return [occupancy_calculator.to_latest_analysis_item(analysis) for analysis in stored_analyses]


@app.get("/vision/frame/{space_id}")
async def get_latest_annotated_frame(space_id: str):
    """
    Devuelve la última foto anotada (con las cajas de detección dibujadas)
    capturada por el scheduler para un espacio con cámara IP real, para que
    la app pueda mostrar visualmente que el tracking es real. Antes del
    primer ciclo, o si el espacio no tiene cámara real, no hay frame guardado.

    @param space_id: identificador del espacio
    @return: imagen JPEG anotada, o 404 si todavía no hay ninguna guardada
    """
    frame_bytes = storage.get_frame(space_id)
    if frame_bytes is None:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "message": f"Todavía no hay un frame analizado para '{space_id}'"},
        )

    return Response(content=frame_bytes, media_type="image/jpeg")
