import os
import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT legacy (tests y login local). En producción usar variables de entorno.
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "llave_login")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Llave pública de Clerk (RS256) — se carga desde .env
CLERK_PEM_PUBLIC_KEY = os.getenv("CLERK_PEM_PUBLIC_KEY", "")

# Como las rutas están versionadas, Swagger debe apuntar al login correcto
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/usuarios/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verificar_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def crear_token_acceso(data: dict) -> str:
    """Genera un token JWT legacy firmado con expiración (usado por tests/login local)."""
    a_copiar = data.copy()
    expiracion = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    a_copiar.update({"exp": expiracion})
    return jwt.encode(a_copiar, SECRET_KEY, algorithm=ALGORITHM)


def _decodificar_clerk(token: str) -> dict:
    """Valida un token de Clerk (RS256) y normaliza los datos del usuario."""
    payload = jwt.decode(token, CLERK_PEM_PUBLIC_KEY, algorithms=["RS256"])
    user_id = payload.get("sub")
    metadata = payload.get("metadata", {})
    rol = metadata.get("rol", "estudiante")
    if user_id is None:
        raise jwt.PyJWTError("token de Clerk sin 'sub'")
    return {"user_id": user_id, "rol": rol}


def _decodificar_legacy(token: str) -> dict:
    """Valida un token JWT propio (HS256) — camino usado por los tests."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    email = payload.get("sub")
    rol = payload.get("rol")
    nombre = payload.get("nombre")
    if email is None or rol is None:
        raise jwt.PyJWTError("token legacy incompleto")
    return {"email": email, "rol": rol, "nombre": nombre}


async def obtener_usuario_actual(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Dependencia para proteger endpoints.
    Intenta primero validar el token como Clerk (RS256); si no hay llave
    configurada o falla, cae al JWT legacy (HS256).
    """
    credenciales_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales o el token expiró",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if CLERK_PEM_PUBLIC_KEY:
        try:
            return _decodificar_clerk(token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="El token ha expirado")
        except jwt.PyJWTError:
            pass  # no era un token de Clerk: probar legacy
    try:
        return _decodificar_legacy(token)
    except jwt.PyJWTError:
        raise credenciales_exception


def requerir_roles(*roles_permitidos: str):
    """Crea una dependencia para permitir acceso únicamente a ciertos roles."""
    async def validador_rol(usuario_actual: dict = Depends(obtener_usuario_actual)) -> dict:
        rol_usuario = usuario_actual.get("rol")

        # Comparación sin distinguir mayúsculas: el JWT legacy usa "Docente"
        # (RoleEnum) y Clerk publicMetadata usa "docente" — ambos deben pasar.
        roles_normalizados = {r.lower() for r in roles_permitidos}
        if (rol_usuario or "").lower() not in roles_normalizados:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso no autorizado. Roles permitidos: {', '.join(roles_permitidos)}",
            )

        return usuario_actual

    return validador_rol
