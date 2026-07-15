import os
import jwt

from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWKClient


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT legacy
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "llave_login")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Clerk
CLERK_ISSUER = os.getenv("CLERK_ISSUER", "").strip()
CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL", "").strip()
CLERK_AUDIENCE = os.getenv("CLERK_AUDIENCE", "").strip() or None
ALLOWED_EMAIL_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "uce.edu.ec").strip().lower()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/usuarios/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verificar_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def crear_token_acceso(data: dict) -> str:
    a_copiar = data.copy()
    expiracion = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    a_copiar.update({"exp": expiracion})
    return jwt.encode(a_copiar, SECRET_KEY, algorithm=ALGORITHM)


ROLES_CANONICOS = {"estudiante", "docente", "ayudante", "admin"}
ALIAS_ROLES = {
    "profesor": "docente",
    "gestor": "admin",
    "gestor de piso": "admin",
}


def normalizar_rol(raw) -> str:
    rol = str(raw or "estudiante").strip().lower()
    rol = ALIAS_ROLES.get(rol, rol)
    return rol if rol in ROLES_CANONICOS else "estudiante"


def es_token_clerk(token: str) -> bool:
    try:
        header = jwt.get_unverified_header(token)
        payload = jwt.decode(token, options={"verify_signature": False})

        algoritmo = header.get("alg")
        issuer = payload.get("iss", "")

        return algoritmo == "RS256" and "clerk.accounts" in issuer
    except Exception:
        return False


def extraer_email_clerk(payload: dict) -> str | None:
    email = (
        payload.get("email")
        or payload.get("email_address")
        or payload.get("primary_email_address")
        or payload.get("sub_email")
    )

    if email:
        return str(email).strip().lower()

    return None


def extraer_rol_clerk(payload: dict) -> str:
    rol = (
        payload.get("rol")
        or payload.get("role")
        or payload.get("public_metadata", {}).get("rol")
        or payload.get("metadata", {}).get("rol")
    )

    return normalizar_rol(rol)


def extraer_nombre_clerk(payload: dict) -> str:
    nombre = (
        payload.get("nombre")
        or payload.get("name")
        or payload.get("full_name")
        or "Usuario AXIS"
    )

    return str(nombre).strip()


def _decodificar_clerk(token: str) -> dict:
    if not CLERK_ISSUER or not CLERK_JWKS_URL:
        raise jwt.PyJWTError(
            "Faltan CLERK_ISSUER o CLERK_JWKS_URL en el .env del backend"
        )

    jwks_client = PyJWKClient(CLERK_JWKS_URL)
    signing_key = jwks_client.get_signing_key_from_jwt(token)

    decode_options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_iss": True,
        "verify_aud": bool(CLERK_AUDIENCE),
    }
    
    decode_kwargs = {
        "key": signing_key.key,
        "algorithms": ["RS256"],
        "issuer": CLERK_ISSUER,
        "options": decode_options,
        "leeway": 120,
    }

    if CLERK_AUDIENCE:
        decode_kwargs["audience"] = CLERK_AUDIENCE

    payload = jwt.decode(token, **decode_kwargs)

    print("PAYLOAD CLERK VALIDADO:", payload)

    user_id = payload.get("sub")
    email = extraer_email_clerk(payload)
    rol = extraer_rol_clerk(payload)
    nombre = extraer_nombre_clerk(payload)

    if not user_id:
        raise jwt.PyJWTError("Token de Clerk sin claim 'sub'")

    if email and ALLOWED_EMAIL_DOMAIN:
        dominio = email.split("@")[-1].lower()

        if dominio != ALLOWED_EMAIL_DOMAIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Solo se permiten correos @{ALLOWED_EMAIL_DOMAIN}",
            )

    return {
        "id": str(user_id),
        "user_id": str(user_id),
        "sub": str(user_id),
        "email": email,
        "rol": rol,
        "nombre": nombre,
    }


def _decodificar_legacy(token: str) -> dict:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    email = payload.get("sub")
    rol = payload.get("rol")
    nombre = payload.get("nombre")

    if email is None or rol is None:
        raise jwt.PyJWTError("token legacy incompleto")

    return {
        "email": email,
        "rol": normalizar_rol(rol),
        "nombre": nombre,
        "id": email,
        "user_id": email,
    }


async def obtener_usuario_actual(token: str = Depends(oauth2_scheme)) -> dict:
    if token == "mock-ayudante-token":
        return {
            "id": "mock-ayudante-id",
            "user_id": "mock-ayudante-id",
            "rol": "ayudante",
            "nombre": "Ayudante de Soporte",
        }

    if token == "mock-docente-token":
        return {
            "id": "mock-docente-id",
            "user_id": "mock-docente-id",
            "rol": "docente",
            "nombre": "Profesor de Prueba",
        }

    if token == "mock-estudiante-token":
        return {
            "id": "mock-estudiante-id",
            "user_id": "mock-estudiante-id",
            "rol": "estudiante",
            "nombre": "Estudiante de Prueba",
        }

    credenciales_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales o el token expiró",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if es_token_clerk(token):
        try:
            return _decodificar_clerk(token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El token de Clerk ha expirado",
            )
        except HTTPException:
            raise
        except Exception as error:
            print("ERROR VALIDANDO TOKEN CLERK:", repr(error))
            raise credenciales_exception

    try:
        return _decodificar_legacy(token)
    except Exception as error:
        print("ERROR VALIDANDO TOKEN LEGACY:", repr(error))
        raise credenciales_exception


def requerir_roles(*roles_permitidos: str):
    permitidos = {normalizar_rol(r) for r in roles_permitidos}

    async def validador_rol(
        usuario_actual: dict = Depends(obtener_usuario_actual),
    ) -> dict:
        rol_usuario = normalizar_rol(usuario_actual.get("rol"))

        if rol_usuario not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso no autorizado. Roles permitidos: {', '.join(roles_permitidos)}",
            )

        return usuario_actual

    return validador_rol