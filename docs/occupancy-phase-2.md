# Axis: Fase 2 - Ocupación Inteligente (Visión Artificial Mock)

Esta documentación describe la arquitectura y el funcionamiento de la **Fase 2** del módulo de ocupación inteligente para el proyecto Axis.

## 1. Qué hace la Fase 2
En esta fase, Axis no usa cámaras reales. El sistema analiza imágenes o videos locales de prueba para validar la arquitectura de visión artificial. La app móvil no procesa imágenes directamente; solo consume métricas calculadas por el backend.

El flujo es el siguiente:
1. **Frontend (Expo)**: El estudiante entra a la lista de bibliotecas o ve un espacio recomendado y toca el botón "Actualizar con visión IA".
2. **Backend Principal**: Recibe la petición en el endpoint `POST /api/occupancy/spaces/{space_id}/analyze`. Construye el payload incluyendo la ruta de la imagen o video de prueba mapeada a ese espacio.
3. **Microservicio de Visión (`vision-service`)**: Recibe la petición en `POST /vision/analyze`. Carga un modelo YOLOv8 local y cuenta la cantidad de personas (clase `person`) en el archivo multimedia enviado.
4. **Respuesta**: El vision-service calcula los asientos libres, el porcentaje de ocupación y el estado (Disponible, Próximo, Ocupado) basándose en las personas detectadas. El Backend Principal combina esta data con la información estática del espacio y se la retorna a la aplicación móvil.

## 2. Qué NO hace todavía (Pendiente para Fase 3)
- No hay cámaras IP conectadas en tiempo real.
- No hay guardado persistente en una Base de Datos real. Las consultas se hacen "on-demand" y sobre datos simulados (`mock_data.py`).
- No se realiza detección ni reconocimiento facial. El modelo solo cuenta cajas delimitadoras (`bounding boxes`) correspondientes a personas de forma completamente anónima.

## 3. Estructura del Vision Service
El código fuente del microservicio de visión se encuentra en la carpeta `vision-service/` dentro del repositorio del Backend Principal.

- `app/main.py`: Endpoints de FastAPI (`/vision/health` y `/vision/analyze`).
- `app/detector.py`: Carga el modelo de Ultralytics YOLO (`yolov8n.pt`) y maneja el conteo de personas en fotos o videos usando OpenCV.
- `app/occupancy_calculator.py`: Transforma los conteos de personas en métricas de negocio (porcentajes de ocupación, estados lógicos, y aplica fallback si falla el modelo).

## 4. Cómo levantar el Vision Service

**Requisitos**: Python 3.10+ instalado.

1. Abre una terminal (PowerShell recomendada) y navega a la carpeta del microservicio:
   ```powershell
   cd vision-service
   ```
2. Crea y activa un entorno virtual de Python:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Instala las dependencias de visión (YOLO, OpenCV, etc.):
   ```powershell
   pip install -r requirements.txt
   ```
4. Inicia el servidor usando Uvicorn:
   ```powershell
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
   ```
> El servicio quedará corriendo en el puerto `8001`. El backend principal de Axis espera encontrarlo allí (a menos que se cambie la variable de entorno `VISION_SERVICE_URL`).

## 5. Pruebas y Validación

### Probar el vision-service directamente
Desde otra ventana de PowerShell, puedes enviar un payload simulado para verificar que YOLO esté infiriendo correctamente:

```powershell
$body = @{
  spaceId = "biblioteca-fica"
  spaceName = "Biblioteca FICA"
  totalSeats = 40
  computersTotal = 12
  sourceType = "sample_image"
  sourcePath = "samples/BIBLIO1.jpg"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8001/vision/analyze" -Method POST -Body $body -ContentType "application/json"
```

### Probar desde la App (Frontend)
1. Inicia el `vision-service` (puerto 8001).
2. Inicia el Backend principal (puerto 8000).
3. Inicia la aplicación móvil Expo y asegúrate de que apunte a la IP de tu red local.
4. Toca "Actualizar con visión IA" en la tarjeta de la Biblioteca FICA.
5. Deberás ver que la información se actualiza, la tarjeta muestra el loader, y al finalizar cambia su "Fuente" a "Visión IA" con las métricas derivadas de la imagen `BIBLIO1.jpg`.

## 6. Fallback Resiliente
Si el `vision-service` está apagado o falla, el Backend Principal detectará el error y retornará un indicador `usedFallback = True`. La aplicación móvil seguirá funcionando y mostrará que la fuente es "Simulado", garantizando que el usuario nunca vea la app romperse.
