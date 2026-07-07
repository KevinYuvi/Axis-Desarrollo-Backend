from typing import Dict, List, Optional

# Almacenamiento en memoria del último análisis por espacio (Fase 3 — sin
# base de datos todavía). Es seguro sin locks porque tanto el scheduler como
# los endpoints corren como tareas cooperativas en el mismo event loop de
# asyncio: nunca se interrumpe una operación de dict a mitad de camino.
_last_analysis: Dict[str, dict] = {}


def save_analysis(space_id: str, analysis: dict) -> None:
    """
    Guarda (o reemplaza) el último resultado de análisis de un espacio.

    @param space_id: identificador del espacio analizado
    @param analysis: resultado del análisis, en formato AnalyzeData serializado
    """
    _last_analysis[space_id] = analysis


def get_analysis(space_id: str) -> Optional[dict]:
    """
    Obtiene el último resultado guardado para un espacio.

    @param space_id: identificador del espacio
    @return: último análisis guardado, o None si todavía no se analizó
    """
    return _last_analysis.get(space_id)


def get_all_analysis() -> List[dict]:
    """
    Obtiene los últimos resultados guardados de todos los espacios ya analizados.

    @return: lista de análisis guardados (puede venir vacía antes del primer ciclo del scheduler)
    """
    return list(_last_analysis.values())
