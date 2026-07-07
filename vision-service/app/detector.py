from pathlib import Path
from typing import Optional

from app import config

# Nombre de la clase COCO que representa personas en los pesos por defecto de YOLO
PERSON_CLASS_NAME = "person"

_yolo_model = None
_yolo_load_failed = False


def _load_yolo_model():
    """
    Carga de forma perezosa el modelo YOLO configurado, cacheando el resultado
    (éxito o fallo) para no reintentar la descarga/carga en cada request.
    Nunca lanza: si ultralytics no está instalado o no hay pesos disponibles
    (por ejemplo sin conexión a internet), devuelve None para que el análisis
    caiga al modo simulado.

    @return: instancia de YOLO lista para inferencia, o None si no está disponible
    """
    global _yolo_model, _yolo_load_failed

    if _yolo_model is not None:
        return _yolo_model
    if _yolo_load_failed:
        return None

    try:
        from ultralytics import YOLO
        _yolo_model = YOLO(config.YOLO_MODEL_PATH)
        return _yolo_model
    except Exception:
        _yolo_load_failed = True
        return None


def _count_person_boxes(detection_result, model) -> int:
    """
    Cuenta las cajas detectadas cuya clase corresponde a "person" y superan
    el umbral de confianza configurado.

    @param detection_result: resultado de inferencia de Ultralytics para un frame/imagen
    @param model: instancia de YOLO usada (para resolver nombres de clase)
    @return: cantidad de personas detectadas en ese resultado
    """
    class_names = model.names
    person_count = 0

    for box in detection_result.boxes:
        class_id = int(box.cls[0])
        confidence = float(box.conf[0])
        if class_names.get(class_id) == PERSON_CLASS_NAME and confidence >= config.PERSON_CONFIDENCE_THRESHOLD:
            person_count += 1

    return person_count


def count_people_in_image(image_path: Path) -> Optional[int]:
    """
    Detecta personas en una imagen local usando YOLO.

    @param image_path: ruta local de la imagen de prueba
    @return: cantidad de personas detectadas, o None si el modelo no está disponible
    """
    model = _load_yolo_model()
    if model is None:
        return None

    results = model(str(image_path), verbose=False)
    return _count_person_boxes(results[0], model)


def count_people_in_video(video_path: Path) -> Optional[int]:
    """
    Detecta personas en un video local muestreando varios frames distribuidos
    a lo largo del clip y promediando el conteo (representa mejor la ocupación
    "típica" del espacio que solo el pico máximo).

    @param video_path: ruta local del video de prueba
    @return: cantidad promedio de personas detectadas, o None si no se pudo procesar
    """
    model = _load_yolo_model()
    if model is None:
        return None

    try:
        import cv2
    except Exception:
        return None

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return None

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    frame_step = max(total_frames // config.MAX_VIDEO_SAMPLE_FRAMES, 1)

    frame_person_counts = []
    frame_index = 0

    while len(frame_person_counts) < config.MAX_VIDEO_SAMPLE_FRAMES and frame_index < total_frames:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        frame_read_ok, frame = capture.read()
        if not frame_read_ok:
            break

        results = model(frame, verbose=False)
        frame_person_counts.append(_count_person_boxes(results[0], model))
        frame_index += frame_step

    capture.release()

    if not frame_person_counts:
        return None

    return round(sum(frame_person_counts) / len(frame_person_counts))
