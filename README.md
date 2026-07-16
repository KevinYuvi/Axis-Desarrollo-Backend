# Axis — Backend

Backend del sistema **Axis**, una aplicación Smart Campus para la Universidad Central del Ecuador que muestra en tiempo real la ocupación de bibliotecas y espacios de estudio, usando visión artificial sobre cámaras IP.

Este repositorio contiene dos servicios:

| Servicio | Tecnología | Puerto | Dónde corre |
|---|---|---|---|
| **API principal** | FastAPI + MongoDB | 8000 | Docker |
| **vision-service** | FastAPI + YOLOv8 (Ultralytics) | 8001 | Local (fuera de Docker) |

---

## Arquitectura y decisiones técnicas

### Monolito modular (API principal)

La API principal es un **monolito modular**: un solo proceso FastAPI, con el código organizado en módulos independientes por dominio de negocio dentro de `app/` (`usuarios`, `espacios`, `reservas`, `reportes`, `ocupacion`, `ia`). Cada módulo tiene su propio `router.py`, `schemas.py` y lógica, y todos se montan bajo el prefijo común `/api/v1`.

**Por qué monolito y no microservicios:** somos un equipo pequeño con un solo despliegue. Un monolito modular nos da la separación de responsabilidades de los microservicios (cada dominio vive aislado en su carpeta y se puede razonar por separado) sin pagar el costo operativo de orquestar, versionar y comunicar varios servicios. Si un módulo crece, su frontera ya está definida y extraerlo después es viable.

### vision-service como servicio separado

El análisis de visión artificial **sí** vive en un proceso aparte, con su propio entorno virtual y su propia API. La razón es práctica, no dogmática:

- **Dependencias pesadas:** PyTorch y Ultralytics pesan varios GB. Meterlas en la imagen Docker de la API principal haría el build lentísimo y la imagen enorme, para algo que solo necesita un módulo.
- **Ciclo de vida distinto:** el modelo YOLO tarda en cargar y consume CPU de forma sostenida. Si el análisis se cae o se reinicia, la API principal no debe verse afectada.
- **Resiliencia por diseño:** la API principal consume al vision-service por HTTP (`VISION_SERVICE_URL`) y, si no responde, degrada a datos simulados en lugar de fallar. Apagar el vision-service nunca rompe la aplicación.

El vision-service ejecuta un **scheduler** que cada 10 segundos captura una foto de la cámara IP configurada, cuenta las personas con YOLOv8, calcula el porcentaje de ocupación y guarda además el último frame anotado (con las cajas de detección dibujadas) para que la app pueda mostrarlo.

### Otras decisiones

- **FastAPI:** framework async con validación de datos vía Pydantic y documentación Swagger generada automáticamente en `/docs`. Encaja con Motor (driver async de MongoDB) sin bloquear el event loop.
- **MongoDB:** los documentos flexibles se adaptan bien a entidades que evolucionan rápido durante el desarrollo (espacios, reservas, reportes) y evitan migraciones de esquema en cada sprint.
- **Docker Compose:** levanta API + base de datos con un solo comando, con las mismas versiones en cualquier máquina. El volumen `mongo_data` conserva los datos entre reinicios.
- **Autenticación híbrida:** los tokens de sesión los emite **Clerk** (RS256) y el backend los verifica con la llave pública de la instancia del equipo. Se mantiene un fallback de JWT propio (`JWT_SECRET_KEY`) solo para desarrollo y tests.
- **Polling en lugar de WebSockets:** el estado de ocupación cambia cada 10 segundos como máximo (ritmo del scheduler), así que un polling simple del cliente con el mismo intervalo entrega la misma frescura de datos sin agregar infraestructura de tiempo real.

---

## Requisitos previos

- **Docker Desktop** (con la virtualización habilitada en el equipo)
- **Python 3.10+** (para el vision-service, que corre fuera de Docker)
- **Git**
- Para la prueba con cámara real: un celular Android con la app **IP Webcam** (de Pavel Khlebovich), conectado a la misma red WiFi que la PC.

---

## Puesta en marcha

### 1. Clonar y configurar variables de entorno

```bash
git clone https://github.com/KevinYuvi/Axis-Desarrollo-Backend.git
cd Axis-Desarrollo-Backend
copy .env.example .env
```

Editar `.env` con los valores reales:

| Variable | Qué es | De dónde sale |
|---|---|---|
| `MONGO_URI` | Conexión a MongoDB para ejecución local | Dejar el valor del ejemplo (dentro de Docker se sobreescribe automáticamente) |
| `JWT_SECRET_KEY` | Llave del JWT legacy | Solo desarrollo/tests; cualquier string |
| `CLERK_PEM_PUBLIC_KEY` | Llave pública para verificar tokens de Clerk | Dashboard de Clerk del equipo → API Keys → *Show JWT public key* (formato PEM) |
| `OPENAI_API_KEY` | Llave del módulo de IA (`app/ia`) | Cuenta de OpenAI del equipo |

### 2. Levantar API principal + MongoDB (Docker)

> Importante: el comando se ejecuta **dentro de la carpeta del repositorio** (ahí vive `docker-compose.yml`).

```bash
docker compose up --build
```

La primera vez tarda varios minutos (descarga imágenes e instala dependencias). Cuando termine:

- API y Swagger: <http://localhost:8000/docs>
- MongoDB: `localhost:27017` (usuario `root`, contraseña `axis2026`)

Para apagar: `docker compose down` (los datos de Mongo se conservan en el volumen).

### 3. Levantar el vision-service (local)

Tiene su propio entorno virtual porque sus dependencias (PyTorch, Ultralytics, OpenCV) son pesadas y no se comparten con la API principal.

```powershell
cd vision-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt   # la primera vez tarda varios minutos
```

Configurar la cámara: encender el servidor de **IP Webcam** en el celular-cámara, anotar la IP que muestra (ej. `192.168.18.3`) y apuntar el servicio a esa dirección — editando el default de `IP_CAMERA_SNAPSHOT_URL` en `app/config.py` o exportando la variable antes de arrancar:

```powershell
$env:IP_CAMERA_SNAPSHOT_URL = "http://192.168.18.3:8080/shot.jpg"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

El `--host 0.0.0.0` es obligatorio para que otros dispositivos de la red puedan conectarse. En la consola, tras ~10 segundos, debe aparecer `Ciclo de análisis automático completado: 5 espacios...`.

### 4. Verificar

```
GET http://localhost:8001/vision/latest                      → análisis de los 5 espacios
GET http://localhost:8000/api/v1/ocupacion/spaces            → los mismos datos vía API principal
GET http://localhost:8000/api/v1/ocupacion/spaces/biblioteca-cisco/frame → última foto anotada por YOLO
```

En la respuesta, `"source": "vision-service"` indica análisis real de cámara; `"vision-service-fallback"` indica dato simulado (espacio sin cámara o cámara inalcanzable).

### 5. Datos semilla

Con MongoDB arriba (paso 2), poblar la colección `espacios` con los edificios reales del campus:

```powershell
python seed.py
```

El script **borra y repuebla** la colección `espacios` con los edificios reales (Edificio A, Edificio de Laboratorios, Bibliotecas y edificios de contexto). Incluye la **Biblioteca Cisco de la Universidad Central** con `svg_id: biblioteca-cisco`, que enlaza el espacio académico con el módulo de ocupación por cámara.

---

## Estructura del repositorio

```
Axis-Desarrollo-Backend/
├── main.py                  # Punto de entrada de la API principal
├── app/
│   ├── database.py          # Conexión a MongoDB (Motor)
│   ├── usuarios/            # Autenticación y roles
│   ├── espacios/            # Aulas y espacios académicos
│   ├── reservas/            # Reservas de espacios
│   ├── reportes/            # Reportes de incidencias
│   ├── ocupacion/           # Ocupación en tiempo real (consume vision-service)
│   └── ia/                  # Asistente con OpenAI
├── vision-service/          # Servicio independiente de visión artificial
│   ├── app/
│   │   ├── scheduler.py     # Ciclo de análisis automático (cada 10 s)
│   │   ├── detector.py      # Detección de personas con YOLOv8
│   │   ├── space_registry.py# Espacios monitoreados y su fuente de imagen
│   │   └── config.py        # Configuración (URL de la cámara, umbrales)
│   └── requirements.txt
├── docker-compose.yml       # API principal + MongoDB
└── .env.example             # Plantilla de variables de entorno
```

---

## Tests

```powershell
# API principal (desde la raíz, con el venv del backend activo)
python -m pytest app/ -v

# vision-service (desde vision-service/, con su venv activo)
python -m pytest . -v
```

Estado conocido: hay una falla preexistente en `app/reportes/test_reportes.py::test_crear_reporte_valido` (heredada de `develop`, sin relación con el módulo de ocupación), pendiente de corrección.

---

## Solución de problemas

- **`no configuration file provided: not found` al correr Docker:** estás fuera de la carpeta del repositorio; el `docker-compose.yml` vive en la raíz de `Axis-Desarrollo-Backend`.
- **Los celulares no llegan a la API:** confirmar que ambos servicios corren con `--host 0.0.0.0` y que el Firewall de Windows permite a Python/Docker en redes privadas (el aviso aparece la primera vez que se levanta cada servicio).
- **Los dispositivos no se ven entre sí en la WiFi:** redes institucionales suelen tener aislamiento de clientes (AP isolation). Usar una red doméstica o el hotspot de un celular para conectar PC y celulares.
- **La cámara dejó de analizarse (`vision-service-fallback` en biblioteca-cisco):** la IP del celular-cámara probablemente cambió al reconectarse a la red. Verificar la IP en la app IP Webcam y actualizarla (paso 3).
- **La base de datos está vacía tras el primer arranque:** es lo esperado — ejecutar `python seed.py` (paso 5) para poblar la colección `espacios`. Las reservas y reportes se crean desde la API (Swagger) o desde la app. El módulo de ocupación no depende de MongoDB.
