import hashlib
import logging
from pathlib import Path
from typing import Optional

import httpx
import numpy as np

from app import config

logger = logging.getLogger("axis.vision.detector")

PERSON_CLASS_NAME = "person"

_yolo_model = None
_yolo_load_failed = False


def _resolve_model_path():
    model_path = Path(config.YOLO_MODEL_PATH)

    if model_path.is_absolute():
        return str(model_path)

    local_model_path = config.SERVICE_ROOT_DIR / model_path

    if local_model_path.exists():
        return str(local_model_path)

    return config.YOLO_MODEL_PATH


def _load_yolo_model():
    global _yolo_model, _yolo_load_failed

    if _yolo_model is not None:
        return _yolo_model

    if _yolo_load_failed:
        return None

    try:
        from ultralytics import YOLO

        resolved_model_path = _resolve_model_path()

        logger.info("Cargando modelo YOLO desde: %s", resolved_model_path)

        _yolo_model = YOLO(resolved_model_path)

        logger.info("Modelo YOLO cargado correctamente.")

        return _yolo_model

    except Exception as error:
        _yolo_load_failed = True
        logger.exception("No se pudo cargar el modelo YOLO: %s", error)
        return None


def _count_person_boxes(detection_result, model) -> int:
    class_names = model.names
    person_count = 0

    for box in detection_result.boxes:
        class_id = int(box.cls[0])
        confidence = float(box.conf[0])

        if (
            class_names.get(class_id) == PERSON_CLASS_NAME
            and confidence >= config.PERSON_CONFIDENCE_THRESHOLD
        ):
            person_count += 1

    return person_count


def count_people_in_image(image_path: Path) -> Optional[int]:
    model = _load_yolo_model()

    if model is None:
        logger.error("No se pudo analizar imagen porque YOLO no está cargado.")
        return None

    if not image_path.exists():
        logger.error("La imagen no existe: %s", image_path)
        return None

    try:
        logger.info("Analizando imagen local: %s", image_path)
        results = model(str(image_path), verbose=False)
        people_count = _count_person_boxes(results[0], model)

        logger.info("Personas detectadas en imagen: %s", people_count)

        return people_count

    except Exception as error:
        logger.exception("Error analizando imagen local: %s", error)
        return None


def count_people_in_video(video_path: Path) -> Optional[int]:
    model = _load_yolo_model()

    if model is None:
        logger.error("No se pudo analizar video porque YOLO no está cargado.")
        return None

    if not video_path.exists():
        logger.error("El video no existe: %s", video_path)
        return None

    try:
        import cv2
    except Exception as error:
        logger.exception("No se pudo importar OpenCV para video: %s", error)
        return None

    try:
        logger.info("Analizando video local: %s", video_path)

        capture = cv2.VideoCapture(str(video_path))

        if not capture.isOpened():
            logger.error("No se pudo abrir el video: %s", video_path)
            return None

        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        frame_step = max(total_frames // config.MAX_VIDEO_SAMPLE_FRAMES, 1)

        frame_person_counts = []
        frame_index = 0

        while (
            len(frame_person_counts) < config.MAX_VIDEO_SAMPLE_FRAMES
            and frame_index < total_frames
        ):
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

            frame_read_ok, frame = capture.read()

            if not frame_read_ok:
                break

            results = model(frame, verbose=False)
            frame_person_counts.append(_count_person_boxes(results[0], model))

            frame_index += frame_step

        capture.release()

        if not frame_person_counts:
            logger.error("No se pudo leer ningún frame del video.")
            return None

        people_count = round(sum(frame_person_counts) / len(frame_person_counts))

        logger.info("Personas promedio detectadas en video: %s", people_count)

        return people_count

    except Exception as error:
        logger.exception("Error analizando video local: %s", error)
        return None


def _get_frame_from_ip_camera(snapshot_url: str):
    try:
        logger.info("Solicitando snapshot de cámara IP: %s", snapshot_url)

        response = httpx.get(snapshot_url, timeout=8.0)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        logger.info(
            "Snapshot recibido. status=%s content-type=%s bytes=%s",
            response.status_code,
            content_type,
            len(response.content),
        )

        if "image" not in content_type.lower():
            logger.error(
                "La URL no devolvió una imagen. content-type=%s",
                content_type,
            )
            return None, None

        image_array = np.frombuffer(response.content, dtype=np.uint8)

        import cv2

        frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if frame is None:
            logger.error("OpenCV no pudo decodificar la imagen recibida.")
            return None, None

        frame_hash = hashlib.md5(response.content).hexdigest()[:12]

        logger.info(
            "Frame de cámara decodificado correctamente. shape=%s hash=%s",
            frame.shape,
            frame_hash,
        )

        return frame, frame_hash

    except Exception as error:
        logger.exception("No se pudo obtener frame desde cámara IP: %s", error)
        return None, None


def count_people_in_ip_camera_snapshot(snapshot_url: str) -> Optional[int]:
    model = _load_yolo_model()

    if model is None:
        logger.error("No se pudo analizar cámara porque YOLO no está cargado.")
        return None

    frame, frame_hash = _get_frame_from_ip_camera(snapshot_url)

    if frame is None:
        return None

    try:
        logger.info("Analizando frame de cámara con YOLO. hash=%s", frame_hash)

        results = model(frame, verbose=False)
        people_count = _count_person_boxes(results[0], model)

        logger.info(
            "Personas detectadas en cámara IP: %s. frameHash=%s",
            people_count,
            frame_hash,
        )

        return people_count

    except Exception as error:
        logger.exception("Error ejecutando YOLO sobre cámara IP: %s", error)
        return None


def _draw_person_boxes(frame, detection_result, model):
    import cv2

    annotated_frame = frame.copy()
    class_names = model.names

    for box in detection_result.boxes:
        class_id = int(box.cls[0])
        confidence = float(box.conf[0])

        if (
            class_names.get(class_id) != PERSON_CLASS_NAME
            or confidence < config.PERSON_CONFIDENCE_THRESHOLD
        ):
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0])

        cv2.rectangle(
            annotated_frame,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2,
        )

        label = f"persona {confidence:.0%}"

        cv2.putText(
            annotated_frame,
            label,
            (x1, max(y1 - 8, 0)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

    return annotated_frame


def analyze_ip_camera_snapshot(snapshot_url: str) -> Optional[dict]:
    model = _load_yolo_model()

    if model is None:
        logger.error("No se pudo anotar cámara porque YOLO no está cargado.")
        return None

    frame, frame_hash = _get_frame_from_ip_camera(snapshot_url)

    if frame is None:
        return None

    try:
        import cv2

        results = model(frame, verbose=False)

        person_count = _count_person_boxes(results[0], model)
        annotated_frame = _draw_person_boxes(frame, results[0], model)

        encode_ok, encoded_jpeg = cv2.imencode(".jpg", annotated_frame)

        if not encode_ok:
            logger.error("No se pudo codificar el frame anotado como JPG.")
            return None

        logger.info(
            "Frame anotado generado correctamente. personas=%s hash=%s",
            person_count,
            frame_hash,
        )

        return {
            "peopleCount": person_count,
            "annotatedJpeg": encoded_jpeg.tobytes(),
            "frameHash": frame_hash,
        }

    except Exception as error:
        logger.exception("Error generando frame anotado: %s", error)
        return None