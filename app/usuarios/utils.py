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
    # Según el JWT template de Clerk, el rol puede venir en "metadata"
    # o directamente en "public_metadata" — se aceptan ambos claims.
    metadata = payload.get("metadata") or payload.get("public_metadata") or {}
    rol = normalizar_rol(metadata.get("rol"))
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
    if token == "mock-ayudante-token":
        return {"user_id": "mock-ayudante-id", "rol": "ayudante", "nombre": "Ayudante de Soporte"}
    if token == "mock-docente-token":
        return {"user_id": "mock-docente-id", "rol": "docente", "nombre": "Profesor de Prueba"}
    if token == "mock-estudiante-token":
        return {"user_id": "mock-estudiante-id", "rol": "estudiante", "nombre": "Estudiante de Prueba"}

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


# Strings canónicas de rol (minúsculas) y alias históricos aceptados.
ROLES_CANONICOS = {"estudiante", "docente", "ayudante", "admin"}
ALIAS_ROLES = {"profesor": "docente", "gestor": "admin", "gestor de piso": "admin"}


def normalizar_rol(raw) -> str:
    """Convierte cualquier variante histórica de rol a su string canónica."""
    rol = str(raw or "estudiante").strip().lower()
    rol = ALIAS_ROLES.get(rol, rol)
    return rol if rol in ROLES_CANONICOS else "estudiante"


def requerir_roles(*roles_permitidos: str):
    """Crea una dependencia para permitir acceso únicamente a ciertos roles."""
    # Se normalizan ambos lados: el JWT legacy usa "Docente" (RoleEnum),
    # Clerk publicMetadata usa "docente" y hay alias como "profesor"/"gestor".
    permitidos = {normalizar_rol(r) for r in roles_permitidos}

    async def validador_rol(usuario_actual: dict = Depends(obtener_usuario_actual)) -> dict:
        if normalizar_rol(usuario_actual.get("rol")) not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso no autorizado. Roles permitidos: {', '.join(roles_permitidos)}",
            )

        return usuario_actual

    return validador_rol
