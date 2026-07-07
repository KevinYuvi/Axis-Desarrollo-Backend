# Fase 2 — Vision Service (imagen/video local de prueba)

## Qué hace esta fase

Agrega un microservicio Python independiente (`vision-service/`) que analiza
una **imagen o video local de prueba** con YOLO (Ultralytics) y cuenta
personas de forma anónima (clase COCO `"person"`), calculando métricas de
ocupación con el mismo contrato que ya usa Axis desde la Fase 1.

El backend principal (`app/ocupacion/`) consulta ese microservicio a través de
un nuevo endpoint, adapta la respuesta al contrato existente y la entrega al
frontend. Si el vision-service no responde, el backend cae de vuelta a los
datos mock de Fase 1 — la app nunca se rompe por falta de visión artificial.

> En esta fase Axis no usa cámaras reales. El sistema analiza imágenes o
> videos locales de prueba para validar la arquitectura de visión artificial.
> La app móvil no procesa imágenes directamente; solo consume métricas
> calculadas por el backend.

## Qué NO hace todavía

- No usa cámaras reales ni transmisión en vivo.
- No guarda fotos, videos ni rostros — el vision-service no persiste nada.
- No hace reconocimiento facial ni identifica personas — solo cuenta objetos
  de la clase `"person"` de forma anónima.
- No persiste el resultado del análisis: `POST /spaces/:id/analyze` es
  _stateless_. `GET /api/occupancy/spaces` sigue mostrando el mock de Fase 1
  hasta que exista una capa de persistencia (Fase 3).
- No agrega autenticación ni rate-limiting al vision-service.

## Arquitectura

```
Frontend Expo
   |  POST /api/occupancy/spaces/:id/analyze
   v
Backend principal (FastAPI)  --VISION_SERVICE_URL-->  vision-service (FastAPI + YOLO)
   |                                                        |
   | si vision-service no responde:                         | si no existe la imagen/video
   | usa mock de Fase 1 (source: "mock")                    | o YOLO no carga:
   |                                                        | responde simulado
   v                                                        | (source: "vision-service-fallback")
Respuesta unificada (mismo contrato EspacioOcupacion)
```

## Cómo levantar todo

### 1. Vision-service (puerto 8001)

```powershell
cd vision-service
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

No es necesario colocar imágenes reales para probar — sin ellas, el servicio
responde en modo fallback simulado (ver `vision-service/samples/README.md`).

### 2. Backend principal (puerto 8000)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Importante:** siempre usar `--host 0.0.0.0`, no solo `uvicorn main:app --reload`.
Sin ese flag, uvicorn escucha únicamente en `127.0.0.1` (solo la propia PC) y
el celular no puede alcanzarlo por WiFi — cada consulta desde la app se queda
esperando el timeout de red antes de caer al fallback, lo que se siente como
"la app está lenta" aunque los datos sean mock y la consulta en sí sea instantánea.

`VISION_SERVICE_URL` tiene como default `http://localhost:8001` — no hace
falta configurar nada si ambos corren localmente. Otros escenarios:

| Escenario                               | `VISION_SERVICE_URL`                                                           |
| --------------------------------------- | ------------------------------------------------------------------------------ |
| Backend local + vision-service local    | `http://localhost:8001` (default)                                              |
| Backend en Docker, vision-service local | `http://host.docker.internal:8001`                                             |
| Ambos en `docker-compose`               | `http://vision-service:8001` (descomentar el servicio en `docker-compose.yml`) |

### 3. Frontend Expo

Sin cambios respecto a Fase 1: configurar `src/shared/config/api.js` con la
IP local de la PC y `npx expo start`.

## Puertos (referencia única — no deben pisarse entre sí)

| Servicio | Puerto | Quién lo consulta |
|---|---|---|
| Backend principal (FastAPI) | `8000` | Frontend Expo (vía `API_BASE_URL`) |
| Vision-service (FastAPI + YOLO) | `8001` | Solo el backend principal (`VISION_SERVICE_URL`), nunca el frontend directamente |
| MongoDB | `27017` | Solo el backend principal |
| Metro (dev server de Expo) | `8081` (default) | Solo el celular/emulador, gestionado por `expo start` |

El frontend **nunca** habla directo con el vision-service — siempre pasa por
el backend principal, que decide si usarlo o caer al mock. Si ves que el
frontend intenta pegarle a `:8001`, algo está mal configurado en `api.js`.

## Cómo probar

**Vision-service:**

```
GET  http://localhost:8001/vision/health
POST http://localhost:8001/vision/analyze
```

con body:

```json
{
  "spaceId": "biblioteca-fica",
  "spaceName": "Biblioteca FICA",
  "totalSeats": 40,
  "computersTotal": 12,
  "sourceType": "sample_image",
  "sourcePath": "samples/BIBLIO1.jpg"
}
```

**Backend principal:**

```
POST http://localhost:8000/api/occupancy/spaces/biblioteca-fica/analyze
```

- Con vision-service arriba → `message: "Ocupación analizada mediante visión artificial"`.
- Con vision-service apagado → `message: "Vision service no disponible. Mostrando datos simulados."`, `ok: true` (nunca rompe).
- Espacio inexistente → `404`, `ok: false`.

**Frontend:** en `LibrariesScreen`, cada tarjeta tiene el botón
"Actualizar con visión IA" y una etiqueta "Fuente: Visión IA" / "Fuente: Simulado".

## Por qué "se sentía lento" (y cómo confirmar que ya no pasa)

Con datos mock, ninguna consulta debería tardar más que la latencia de red.
Si la app se siente lenta al abrir "Bibliotecas", casi siempre es una de estas
dos causas — no un problema de rendimiento de las consultas en sí:

1. **El backend no escucha en `0.0.0.0`** (ver nota de arriba). Cada request
   del celular se queda esperando el timeout antes de caer al fallback.
2. **Firewall de Windows** bloqueando conexiones entrantes al puerto 8000 desde
   la red local. Si tras usar `--host 0.0.0.0` sigue lento/fallando, revisa que
   el perfil de red sea "Privada" (no "Pública") y permite Python/uvicorn en el
   Firewall de Windows Defender.

Para confirmar que el backend es alcanzable desde el celular, abre el navegador
del celular (mismo WiFi) en `http://TU_IP:8000/docs` — si carga el Swagger,
la conectividad está bien y cualquier lentitud restante es de la red, no del código.

El frontend además comparte un solo estado de ocupación entre "Inicio" y
"Bibliotecas" (`OccupancyProvider`) — navegar entre esas pantallas no vuelve a
consultar el backend, solo la primera carga de la app lo hace.

## Qué queda para Fase 3

- Persistir el resultado del análisis (base de datos) para que `GET /spaces`
  refleje la última ocupación medida, no solo el mock estático.
- Conectar cámaras reales / streaming en vivo en vez de imágenes de prueba.
- Agregación temporal (histórico de ocupación, tendencias por hora).
- Autenticación entre backend principal y vision-service.
- Pantalla de detalle de espacio dedicada en el frontend (hoy la acción vive
  en la tarjeta de la lista).
