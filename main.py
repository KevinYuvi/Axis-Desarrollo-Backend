from fastapi import FastAPI
from app.espacios.router import router as espacios_router
from app.reservas.router import router as reservas_router
from app.reportes.router import router as reportes_router
from app.usuarios.router import router as usuarios_router


app = FastAPI(
    title="AXIS API - Sistema de Gestión Universitaria",
    description="Backend para la gestión de espacios, usuarios, reservas, reportes e incidencias.",
    version="1.0.0",
    )

app.include_router(espacios_router)
app.include_router(reservas_router)
app.include_router(reportes_router)
app.include_router(usuarios_router)



@app.get("/", tags=["Root"])
def read_root():
    return {
        "status": "online",
        "message": "Bienvenido a la API de AXIS Backend",
    }


