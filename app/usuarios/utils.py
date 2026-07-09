import jwt
import os
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer

# Llave pública de Clerk (la pondrás en tu archivo .env del backend)
CLERK_PEM_PUBLIC_KEY = os.getenv("CLERK_PEM_PUBLIC_KEY", "").replace("\\n", "\n")

# No necesitamos tokenUrl porque el login se hace en el celular con Clerk
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="")

async def obtener_usuario_actual(token: str = Depends(oauth2_scheme)) -> dict:
    """Intercepta el token JWT de Clerk, lo valida y extrae el rol[cite: 314]."""
    credenciales_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales de Clerk",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not CLERK_PEM_PUBLIC_KEY:
        print("ADVERTENCIA: Falta CLERK_PEM_PUBLIC_KEY en .env")
        
    try:
        # Decodificamos el JWT de Clerk [cite: 316]
        payload = jwt.decode(token, CLERK_PEM_PUBLIC_KEY, algorithms=["RS256"])
        
        # Clerk guarda el ID de usuario en 'sub' [cite: 316]
        user_id: str = payload.get("sub")
        
        # Extraemos los metadatos públicos (donde guardaremos el rol "admin" o "docente") [cite: 316]
        metadata = payload.get("public_metadata", payload.get("metadata", {}))
        rol: str = metadata.get("rol", "estudiante").lower() # Por defecto estudiante [cite: 316]
        
        if user_id is None:
            raise credenciales_exception
            
        # Retornamos el perfil empaquetado para que los routers lo usen
        return {"user_id": user_id, "id": user_id, "_id": user_id, "rol": rol}
        
    except Exception as e:
        print(f"Error decodificando JWT de Clerk: {e}")
        raise credenciales_exception

def requerir_roles(*roles_permitidos: str):
    """Dependencia para bloquear o permitir acciones según el rol[cite: 582, 583]."""
    async def validador_rol(usuario_actual: dict = Depends(obtener_usuario_actual)) -> dict:
        rol_usuario = usuario_actual.get("rol", "estudiante").lower()
        roles_permitidos_lower = [r.lower() for r in roles_permitidos]

        if rol_usuario not in roles_permitidos_lower:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere ser: {', '.join(roles_permitidos)}",
            )
        return usuario_actual

    return validador_rol