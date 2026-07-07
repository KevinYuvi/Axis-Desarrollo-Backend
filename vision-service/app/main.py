from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import occupancy_calculator
from app.schemas import AnalyzeRequest, AnalyzeResponse, HealthResponse

app = FastAPI(
    title="Axis Vision Service",
    description="Microservicio de visión artificial de Axis (Fase 2 — imagen/video local de prueba).",
    version="0.1.0",
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
    Analiza un espacio a partir de una imagen/video local de prueba y devuelve
    las métricas de ocupación calculadas. Nunca expone detalles internos del
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
