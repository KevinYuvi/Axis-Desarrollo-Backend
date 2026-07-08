import os
import jwt

from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuración de seguridad
SECRET_KEY = os.getenv("SECRET_KEY", "llave_login")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Como las rutas ahora están versionadas, Swagger debe apuntar al login correcto
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/usuarios/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verificar_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def crear_token_acceso(data: dict) -> str:
    """Genera un token JWT firmado con tiempo de expiración."""
    payload = data.copy()
    expiracion = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload.update({"exp": expiracion})

    token_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token_jwt


async def obtener_usuario_actual(token: str = Depends(oauth2_scheme)) -> dict:
    """Valida el JWT y retorna los datos principales del usuario autenticado."""
    credenciales_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales o el token expiró",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        email: str = payload.get("sub")
        rol: str = payload.get("rol")
        nombre: str = payload.get("nombre")
        usuario_id: str | None = payload.get("id")

        if email is None or rol is None:
            raise credenciales_exception

        return {
            "id": usuario_id,
            "email": email,
            "rol": rol,
            "nombre": nombre,
        }

    except jwt.PyJWTError:
        raise credenciales_exception


def requerir_roles(*roles_permitidos: str):
    """Crea una dependencia para permitir acceso únicamente a ciertos roles."""
    async def validador_rol(usuario_actual: dict = Depends(obtener_usuario_actual)) -> dict:
        rol_usuario = usuario_actual.get("rol")

        if rol_usuario not in roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso no autorizado. Roles permitidos: {', '.join(roles_permitidos)}",
            )

        return usuario_actual

    return validador_rol