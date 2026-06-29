from fastapi import FastAPI
from app.espacios.router import router as espacios_router

app = FastAPI(
    title="AXIS API - Sistema de Gestión Universitaria",
    description="Backend desarrollado bajo una arquitectura de Monolito Modular para controlar espacios, reservas e incidencias.",
    version="1.0.0",
    docs_url="/docs",
)

@app.get("/", tags=["Root"])
def read_root():
    return {
        "status": "online",
        "message": "Bienvenido a la API de AXIS Backend",
    }

app.include_router(espacios_router)