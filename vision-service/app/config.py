import os
from pathlib import Path

# Directorio raíz del vision-service
SERVICE_ROOT_DIR = Path(__file__).resolve().parent.parent

# Carpeta de muestras, aunque ahora no la usemos
SAMPLES_DIR = Path(os.getenv("VISION_SAMPLES_DIR", SERVICE_ROOT_DIR / "samples"))

# Modelo YOLO
YOLO_MODEL_PATH = os.getenv("VISION_MODEL_PATH", "yolov8n.pt")

# Umbral mínimo para contar personas
PERSON_CONFIDENCE_THRESHOLD = float(
    os.getenv("VISION_CONFIDENCE_THRESHOLD", "0.35")
)

# Máximo de frames para videos
MAX_VIDEO_SAMPLE_FRAMES = int(
    os.getenv("VISION_VIDEO_SAMPLE_FRAMES", "5")
)

# Cámara IP del celular
IP_CAMERA_SNAPSHOT_URL = os.getenv(
    "IP_CAMERA_SNAPSHOT_URL",
    "http://10.186.95.91:8080/shot.jpg",
)