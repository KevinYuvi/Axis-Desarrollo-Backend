import os
import httpx
from fastapi import HTTPException

CLERK_API_BASE = "https://api.clerk.com/v1"


def _headers() -> dict:
    secret = os.getenv("CLERK_SECRET_KEY", "")
    if not secret:
        raise HTTPException(status_code=500, detail="Falta CLERK_SECRET_KEY en el .env")
    return {"Authorization": f"Bearer {secret}"}


async def listar_usuarios_clerk(limite: int = 100) -> list[dict]:
    """Lista los usuarios de la instancia Clerk con su rol actual."""
    async with httpx.AsyncClient() as cliente:
        resp = await cliente.get(f"{CLERK_API_BASE}/users", headers=_headers(),
                                 params={"limit": limite})
    resp.raise_for_status()
    return [
        {
            "id": u["id"],
            "email": (u.get("email_addresses") or [{}])[0].get("email_address"),
            "nombre": f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip(),
            "rol": (u.get("public_metadata") or {}).get("rol", "estudiante"),
        }
        for u in resp.json()
    ]


async def asignar_rol_clerk(user_id: str, rol: str) -> dict:
    """Escribe public_metadata.rol del usuario en Clerk."""
    async with httpx.AsyncClient() as cliente:
        resp = await cliente.patch(f"{CLERK_API_BASE}/users/{user_id}/metadata",
                                   headers=_headers(),
                                   json={"public_metadata": {"rol": rol}})
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en Clerk")
    resp.raise_for_status()
    return {"id": user_id, "rol": rol}
