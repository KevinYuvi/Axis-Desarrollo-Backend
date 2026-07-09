import asyncio
import logging
from datetime import datetime, timezone

from app import detector, occupancy_calculator, storage
from app.schemas import AnalyzeRequest
from app.space_registry import SPACE_REGISTRY

logger = logging.getLogger("axis.vision.scheduler")

# Cada cuánto se vuelve a analizar todos los espacios del registro.
ANALYSIS_INTERVAL_SECONDS = 10


def _capture_and_store_annotated_frame(space_config: dict) -> None:
    """
    Captura una foto anotada (con las cajas de detección dibujadas) desde la
    cámara IP de un espacio y la guarda en memoria, para que la app pueda
    mostrarla y así verificar visualmente que el tracking es real. También
    registra el hash del frame recibido: si ese hash no cambia entre ciclos,
    significa que la cámara está enviando siempre la misma imagen (por
    ejemplo, porque el celular bloqueó la pantalla y dejó de capturar).
    Nunca lanza: cualquier fallo solo se registra en el log.

    @param space_config: entrada de SPACE_REGISTRY del espacio con cámara real
    """
    result = detector.analyze_ip_camera_snapshot(space_config["sourcePath"])
    if result is None:
        logger.warning("No se pudo capturar/anotar el frame de '%s'", space_config["spaceId"])
        return

    storage.save_frame(space_config["spaceId"], result["annotatedJpeg"])
    logger.info(
        "Frame de '%s' actualizado -> hash=%s, %d persona(s) marcada(s) en la imagen",
        space_config["spaceId"], result["frameHash"], result["peopleCount"],
    )


async def _analyze_and_store_space(space_config: dict) -> None:
    """
    Analiza un espacio del registro y guarda el resultado en el storage en
    memoria. La inferencia (potencialmente lenta con YOLO) corre en un hilo
    aparte para no bloquear el event loop mientras el scheduler trabaja.
    Si el espacio tiene cámara IP real, además captura y guarda el frame
    anotado con las cajas de detección.

    @param space_config: entrada de SPACE_REGISTRY con los datos del espacio
    """
    analyze_request = AnalyzeRequest(**space_config)
    analysis_result = await asyncio.to_thread(occupancy_calculator.analyze_space, analyze_request)
    storage.save_analysis(space_config["spaceId"], analysis_result.model_dump(mode="json"))

    logger.info(
        "Espacio '%s': %s persona(s) detectada(s), %s%% ocupación, estado=%s, fuente=%s, método=%s",
        space_config["spaceId"], analysis_result.peopleCount, analysis_result.occupancyPercent,
        analysis_result.status, analysis_result.source, analysis_result.detectionMethod,
    )

    if space_config["sourceType"] == "ip_camera_snapshot":
        await asyncio.to_thread(_capture_and_store_annotated_frame, space_config)


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
