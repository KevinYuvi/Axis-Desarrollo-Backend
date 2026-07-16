# Axis: Fase 3 - Análisis Automático (Scheduler)

Esta documentación describe la arquitectura y el funcionamiento de la **Fase 3** del módulo de ocupación inteligente para el proyecto Axis.

## 1. Qué hace la Fase 3

En la Fase 2, el vision-service solo analizaba una imagen cuando el usuario tocaba el botón "Actualizar con visión IA" en la app. En esta fase, ese análisis se vuelve **automático y continuo**: el usuario ya no tiene que hacer nada para que la ocupación se actualice.

El flujo es el siguiente:
1. **Vision Service**: un scheduler interno recorre todos los espacios del registro cada 30 segundos, analiza su imagen/video asociado y guarda el resultado en memoria (`last_analysis`).
2. **Backend Principal**: en cada consulta a `GET /api/occupancy/spaces` (o `/spaces/:id`, o `/recommendation`), ya no llama a `POST /vision/analyze`. En su lugar, consulta `GET /vision/latest` y combina ese último análisis con los datos estáticos del espacio (edificio, piso, salas de estudio, distancia, etc.).
3. **Frontend (Expo)**: ya no existe el botón "Actualizar con visión IA". La app hace *polling* — vuelve a consultar el backend cada 30 segundos en segundo plano, sin mostrar el loader de pantalla completa en esos refrescos automáticos.

## 2. Qué NO hace todavía (Pendiente para Fase 4)

- No hay cámaras IP conectadas en tiempo real — el scheduler sigue analizando imágenes/videos **locales** de prueba.
- No hay WebSockets: el frontend usa *polling* cada 30 segundos, no una conexión en tiempo real.
- No hay base de datos: `last_analysis` vive en memoria del vision-service y se pierde si el proceso se reinicia.
- El registro de espacios (`SPACE_REGISTRY`) está duplicado entre el backend (`app/ocupacion/mock_data.py`) y el vision-service (`vision-service/app/space_registry.py`) — no hay todavía una única fuente de verdad compartida.
- No se realiza detección ni reconocimiento facial — el modelo solo cuenta cajas delimitadoras (`bounding boxes`) de personas, de forma completamente anónima.

## 3. Estructura del Vision Service (Fase 3)

Separación por capas dentro de `vision-service/app/`:

- `main.py`: capa API — expone `/vision/health`, `/vision/analyze` (uso manual/debug) y `/vision/latest`; arranca el scheduler al iniciar (`lifespan`).
- `scheduler.py`: dispara un ciclo de análisis completo cada `ANALYSIS_INTERVAL_SECONDS` (30s por defecto), recorriendo `SPACE_REGISTRY`.
- `storage.py`: guarda en memoria el último análisis de cada espacio (`save_analysis` / `get_analysis` / `get_all_analysis`), sin base de datos.
- `space_registry.py`: lista estática de espacios que el scheduler debe analizar (id, capacidad, imagen/video asociado).
- `detector.py`: carga YOLO y cuenta personas en imágenes/video (sin cambios respecto a Fase 2).
- `occupancy_calculator.py`: transforma conteos de personas en métricas de negocio, y adapta ese resultado al contrato liviano de `/vision/latest`.

## 4. Cómo levantar todo

**Requisitos**: Python 3.10+, backend principal y vision-service con sus propios entornos virtuales (ver `docs/occupancy-phase-2.md` para la primera instalación).

**Terminal 1 — Vision Service** (puerto 8001):
```powershell
cd vision-service
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```
Al iniciar, el scheduler corre un primer ciclo inmediatamente (no espera los 30s) y luego se repite solo.

**Terminal 2 — Backend Principal** (puerto 8000):
```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Siempre con `--host 0.0.0.0`, o el celular no podrá alcanzarlo (ver troubleshooting en `docs/occupancy-phase-2.md`).

**Frontend Expo**: sin cambios en cómo se levanta; configurar `src/shared/config/api.js` con la IP local y `npx expo start`.

## 5. Pruebas y Validación

### Verificar que el scheduler corre automáticamente
En la consola del vision-service, sin tocar nada, debe aparecer una línea nueva cada 30 segundos:
```
INFO:axis.vision.scheduler:Ciclo de análisis automático completado: 5 espacios (iniciado ...)
```
Si ves esa línea repetirse sola, el scheduler funciona.

### Probar `GET /vision/latest` directamente
```powershell
Invoke-RestMethod -Uri "http://localhost:8001/vision/latest" -Method GET
```
Debe devolver un arreglo con un elemento por espacio ya analizado (puede venir vacío los primeros segundos tras iniciar).

### Probar que el backend ya no llama a `/vision/analyze`
Con el vision-service arriba, consulta:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/occupancy/spaces/biblioteca-fica" -Method GET
```
El campo `source` debe decir `"vision-service"` (o `"vision-service-fallback"` si no hay imagen real para ese espacio) sin que hayas disparado ninguna acción manual — los datos ya vienen del último ciclo del scheduler.

### Probar desde la app (Frontend)
1. Inicia el vision-service y espera a ver al menos un ciclo completado en su consola.
2. Inicia el backend principal.
3. Abre la app y entra a "Bibliotecas". Ya no hay botón "Actualizar con visión IA".
4. Deja la pantalla abierta 30-60 segundos: la etiqueta "Fuente" y los números de ocupación deben poder cambiar solos si el scheduler recalculó algo distinto, sin que toques nada.

### Prueba de fallback (Fase 2, sigue vigente)
Apaga el vision-service y vuelve a consultar `GET /api/occupancy/spaces` — debe seguir respondiendo `ok: true` con los datos mock de Fase 1, sin romperse.

## 6. Fallback Resiliente

Si el vision-service está apagado, no responde a tiempo, o `GET /vision/latest` devuelve una lista vacía, el Backend Principal simplemente devuelve los espacios base de Fase 1 sin modificar. La aplicación móvil nunca ve un error — en el peor caso, ve datos simulados con `source: "mock"`.

## 7. Qué queda para Fase 4

- Cámaras IP reales o streaming en vivo en lugar de imágenes de prueba.
- Persistencia en base de datos del historial de análisis (no solo el último valor).
- Registro de espacios compartido entre backend y vision-service (una sola fuente de verdad).
- Reemplazar el polling por WebSockets o Server-Sent Events para actualizaciones en tiempo real sin refrescar cada 30 segundos.
