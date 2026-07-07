import asyncio
import logging
from datetime import datetime, timezone

from app import occupancy_calculator, storage
from app.schemas import AnalyzeRequest
from app.space_registry import SPACE_REGISTRY

logger = logging.getLogger("axis.vision.scheduler")

# Cada cuánto se vuelve a analizar todos los espacios del registro.
ANALYSIS_INTERVAL_SECONDS = 30


async def _analyze_and_store_space(space_config: dict) -> None:
    """
    Analiza un espacio del registro y guarda el resultado en el storage en
    memoria. La inferencia (potencialmente lenta con YOLO) corre en un hilo
    aparte para no bloquear el event loop mientras el scheduler trabaja.

    @param space_config: entrada de SPACE_REGISTRY con los datos del espacio
    """
    analyze_request = AnalyzeRequest(**space_config)
    analysis_result = await asyncio.to_thread(occupancy_calculator.analyze_space, analyze_request)
    storage.save_analysis(space_config["spaceId"], analysis_result.model_dump(mode="json"))


async def _run_analysis_cycle() -> None:
    """
    Analiza todos los espacios del registro en una misma pasada. Si un
    espacio falla, se registra el error y se continúa con los demás — un
    espacio roto no debe detener el análisis del resto.
    """
    cycle_started_at = datetime.now(timezone.utc)

    for space_config in SPACE_REGISTRY:
        try:
            await _analyze_and_store_space(space_config)
        except Exception:
            logger.exception("No se pudo analizar el espacio '%s'", space_config["spaceId"])

    logger.info(
        "Ciclo de análisis automático completado: %d espacios (iniciado %s)",
        len(SPACE_REGISTRY),
        cycle_started_at.isoformat(),
    )


async def run_scheduler_loop() -> None:
    """
    Bucle infinito que dispara un ciclo de análisis completo cada
    ANALYSIS_INTERVAL_SECONDS. Se lanza una vez al iniciar la app (ver
    lifespan en main.py) y corre en segundo plano durante toda su vida.
    """
    while True:
        await _run_analysis_cycle()
        await asyncio.sleep(ANALYSIS_INTERVAL_SECONDS)
