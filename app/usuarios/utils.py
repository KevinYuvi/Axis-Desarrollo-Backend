import jwt
import os
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer

# Obtenemos la llave pública de Clerk desde el .env (La configuraremos luego)
CLERK_PEM_PUBLIC_KEY = os.getenv("CLERK_PEM_PUBLIC_KEY", "")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="usuarios/login")

async def obtener_usuario_actual(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Dependencia para proteger endpoints. 
    Intercepta el token JWT de Clerk enviado desde el frontend de Expo,
    lo valida con la llave pública y extrae el rol.
    """
    credenciales_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales de Clerk",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not CLERK_PEM_PUBLIC_KEY:
        print("ADVERTENCIA: Falta CLERK_PEM_PUBLIC_KEY en las variables de entorno")
        
    try:
        # Decodificamos el token JWT asimétrico de Clerk
        payload = jwt.decode(token, CLERK_PEM_PUBLIC_KEY, algorithms=["RS256"])
        
        # Clerk guarda el ID del usuario en 'sub'
        user_id: str = payload.get("sub")
        
        # Extraemos el rol desde los metadatos públicos del token
        metadata = payload.get("metadata", {})
        rol: str = metadata.get("rol", "estudiante") # Por defecto es estudiante
        
        if user_id is None:
            raise credenciales_exception
            
        return {"user_id": user_id, "rol": rol}
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token ha expirado")
    except jwt.PyJWTError as e:
        print(f"Error decodificando JWT: {e}")
        raise credenciales_exception