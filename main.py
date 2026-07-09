from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.espacios.router import router as espacios_router
from app.reservas.router import router as reservas_router
from app.reportes.router import router as reportes_router
from app.ia.router import router as ia_router

API_PREFIX = "/api/v1"

app = FastAPI(
    title="AXIS API - Super Backend Integrado con Clerk",
    description="Backend Monolito Modular con IA, Reservas y Auth delegada a Clerk.",
    version="1.0.0",
)

# CORS para que el frontend pueda conectarse [cite: 588]
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
        "message": "Super Backend AXIS con Clerk operando",
    }

# 🔴 Rutas de Negocio habilitadas[cite: 588]. 
# (La de 'usuarios' ha sido eliminada por completo)
app.include_router(espacios_router, prefix=API_PREFIX)
app.include_router(reservas_router, prefix=API_PREFIX)
app.include_router(reportes_router, prefix=API_PREFIX)
app.include_router(ia_router, prefix=API_PREFIX)