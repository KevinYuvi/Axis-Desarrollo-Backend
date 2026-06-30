import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
import jwt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# CONFIGURACIÓN DE SEGURIDAD (En producción esto va en variables de entorno .env)
SECRET_KEY = "llave_login"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verificar_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def crear_token_acceso(data: dict) -> str:
    """Genera un token JWT firmado con un tiempo de expiración."""
    a_copiar = data.copy()
    # Tiempo de expiración usando hora actual con zona horaria
    expiracion = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Añadimos la fecha de expiración al cuerpo del token (payload)
    a_copiar.update({"exp": expiracion})
    
    # Firmamos el token JWT
    token_jwt = jwt.encode(a_copiar, SECRET_KEY, algorithm=ALGORITHM)
    return token_jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="usuarios/login")

async def obtener_usuario_actual(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependencia para proteger endpoints. Valida el JWT y retorna los datos del usuario."""
    credenciales_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales o el token expiró",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decodificamos el token usando la misma llave secreta
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        rol: str = payload.get("rol")
        nombre: str = payload.get("nombre")
        
        if email is None or rol is None:
            raise credenciales_exception
            
        # Retornamos un diccionario con los datos del usuario autenticado
        return {"email": email, "rol": rol, "nombre": nombre}
        
    except jwt.PyJWTError:
        raise credenciales_exception