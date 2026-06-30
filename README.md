# Backend (Monolito Modular)

Este repositorio contiene el backend del sistema, diseñado bajo una arquitectura de monolito modular con **FastAPI** y persistencia en **MongoDB**, todo contenedorizado con **Docker**.

---

## Requisitos Previos

Antes de ejecutar el proyecto, asegúrate de tener instalado en tu máquina:
* **Docker Desktop**
* **Git**
---

## Cómo Ejecutar el Proyecto con Docker (Recomendado)

Sigue estos pasos para levantar todo el entorno de desarrollo de forma automática:

### 1. Clonar el repositorio y acceder a la carpeta
```bash
git clone https://github.com/KevinYuvi/Axis-Desarrollo-Backend.git
cd Axis-Desarrollo-Backend
```

### 2. Construir y activar los contenedores de Docker
Este comando descargará e instalará todas las dependencias (FastAPI, Uvicorn, MongoDB) automáticamente dentro de un contenedor aislado:
```bash
docker compose up --build
```
* Una vez encendido, podrás acceder a la API en: **http://127.0.0**

### 3. Apagar los contenedores
Para detener el entorno y liberar los puertos cuando termines de trabajar:
```bash
docker compose down
```

---

## Ejecución Local Opcional (Sin Docker)

Si prefieres correr el proyecto directamente en tu entorno virtual local:

### 1. Crear y activar el entorno virtual
```powershell
python -m venv .venv
.\.venv\Scripts\Activate
```

### 2. Instalar las librerías necesarias
```powershell
pip install fastapi uvicorn pydantic pytest
```

### 3. Levantar el servidor y ejecutar pruebas
```powershell
# Iniciar servidor local:
uvicorn main:app --reload

# Ejecutar las pruebas unitarias:
python -m pytest app/ -v
```
---
## Prueba de APIs en Swagger

Puedes ingresar a Swagger para probar las APIs en: **http://localhost:8000/docs**