# Axis Vision Service

Microservicio de visión artificial de Axis (Fase 2). Analiza una imagen o
video **local** de prueba con YOLO y cuenta personas de forma anónima para
calcular métricas de ocupación compatibles con el contrato que ya usa Axis.

No usa cámaras reales, no guarda fotos/videos/rostros, no hace reconocimiento
facial ni identifica personas — solo cuenta objetos de la clase `"person"`.

## Cómo levantarlo (local)

```powershell
cd vision-service
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

> La primera vez que se analiza una imagen, `ultralytics` descarga los pesos
> `yolov8n.pt` (~6 MB) desde internet. Si no hay conexión o falla la descarga,
> el servicio sigue funcionando en modo fallback simulado (ver
> `samples/README.md`), nunca se cae.

## Cómo levantarlo (Docker)

```bash
docker build -t axis-vision-service .
docker run -p 8001:8001 axis-vision-service
```

## Endpoints

### `GET /vision/health`
```json
{ "ok": true, "service": "axis-vision-service", "status": "online" }
```

### `POST /vision/analyze`
Body:
```json
{
  "spaceId": "biblioteca-fica",
  "spaceName": "Biblioteca FICA",
  "totalSeats": 40,
  "computersTotal": 12,
  "sourceType": "sample_image",
  "sourcePath": "samples/biblioteca_fica.jpg"
}
```
Respuesta (con detección real o en modo fallback si falta el archivo o el
modelo no está disponible — ver `data.source`):
```json
{
  "ok": true,
  "message": "Análisis de ocupación generado correctamente",
  "data": {
    "spaceId": "biblioteca-fica",
    "spaceName": "Biblioteca FICA",
    "peopleCount": 18,
    "totalSeats": 40,
    "occupiedSeats": 18,
    "freeSeats": 22,
    "computersTotal": 12,
    "computersAvailable": 5,
    "occupancyPercent": 45,
    "status": "Disponible",
    "source": "vision-service",
    "detectionMethod": "yolo_local_sample",
    "aiEnabled": true,
    "updatedAt": "2026-07-07T15:00:00Z"
  }
}
```

## Configuración (variables de entorno opcionales)

| Variable | Default | Descripción |
|---|---|---|
| `VISION_SAMPLES_DIR` | `./samples` | Carpeta de imágenes/videos de prueba |
| `VISION_MODEL_PATH` | `yolov8n.pt` | Pesos de YOLO a cargar |
| `VISION_CONFIDENCE_THRESHOLD` | `0.35` | Confianza mínima para contar una detección |
| `VISION_VIDEO_SAMPLE_FRAMES` | `5` | Frames muestreados por video analizado |
| `VISION_FALLBACK_OCCUPANCY_RATIO` | `0.4` | Ocupación simulada en modo fallback |

## Integración con el backend principal

Ver `docs/occupancy-phase-2.md` en la raíz del repositorio backend.
