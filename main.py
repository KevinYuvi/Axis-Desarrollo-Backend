from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.espacios.router import router as espacios_router
from app.reservas.router import router as reservas_router
from app.reportes.router import router as reportes_router
from app.usuarios.router import router as usuarios_router
from app.ocupacion.router import router as ocupacion_router
from app.ia.router import router as ia_router

API_PREFIX = "/api/v1"

app = FastAPI(
    title="AXIS API - Sistema de Gestión Universitaria",
    description="Backend desarrollado bajo una arquitectura de Monolito Modular para controlar espacios, reservas e incidencias.",
    version="1.0.0",
    docs_url="/docs",
)

# Habilitado para desarrollo: permite que Expo (celular físico, emulador o
# expo start --web) consuma la API desde cualquier origen local.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["Root"])
def read_root():
    return {
        "status": "online",
        "message": "Bienvenido a la API de AXIS Backend",
    }


app.include_router(espacios_router, prefix=API_PREFIX)
app.include_router(reservas_router, prefix=API_PREFIX)
app.include_router(reportes_router, prefix=API_PREFIX)
app.include_router(usuarios_router, prefix=API_PREFIX)
app.include_router(ia_router, prefix=API_PREFIX)
# El router de ocupación define su propio prefijo (se estandariza a /api/v1 más adelante)
app.include_router(ocupacion_router)
