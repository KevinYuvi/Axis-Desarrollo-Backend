import os
from pathlib import Path

# Directorio raíz del vision-service (padre de app/)
SERVICE_ROOT_DIR = Path(__file__).resolve().parent.parent

# Carpeta donde se buscan las imágenes/videos de prueba
SAMPLES_DIR = Path(os.getenv("VISION_SAMPLES_DIR", SERVICE_ROOT_DIR / "samples"))

# Modelo de Ultralytics YOLO a cargar (nombre de pesos oficiales o ruta local .pt)
YOLO_MODEL_PATH = os.getenv("VISION_MODEL_PATH", "yolov8n.pt")

# Confianza mínima para contar una detección de clase "person" como válida
PERSON_CONFIDENCE_THRESHOLD = float(os.getenv("VISION_CONFIDENCE_THRESHOLD", "0.35"))

# Cantidad máxima de frames a muestrear al analizar un video de prueba
MAX_VIDEO_SAMPLE_FRAMES = int(os.getenv("VISION_VIDEO_SAMPLE_FRAMES", "5"))

# Proporción usada para simular personas cuando no hay detección real disponible
FALLBACK_OCCUPANCY_RATIO = float(os.getenv("VISION_FALLBACK_OCCUPANCY_RATIO", "0.4"))

# URL de captura de foto de la cámara IP Webcam para el espacio con cámara real
# (Fase 4). Reemplazar por la IP real del celular-cámara antes de probar; ver
# docs/.plans/260708-1317-camera-tracking-realtime/ para el paso a paso.
IP_CAMERA_SNAPSHOT_URL = os.getenv(
    "IP_CAMERA_SNAPSHOT_URL", "http://10.138.168.112:8080/shot.jpg"
)
