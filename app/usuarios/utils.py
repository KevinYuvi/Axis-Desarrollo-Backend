from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
import jwt  # Asegúrate de tener instalado 'pip install pyjwt'

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
    expiracion = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    a_copiar.update({"exp": expiracion})
    
    token_jwt = jwt.encode(a_copiar, SECRET_KEY, algorithm=ALGORITHM)
    return token_jwt

# OAuth2PasswordBearer buscará automáticamente en la cabecera 'Authorization: Bearer <TOKEN>'
# Funciona perfecto incluso con multipart/form-data en Swagger si estás logueado con el botón Authorize.
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
        
        email: str = payload.get("sub")  # Habitualmente 'sub' contiene el email o el id único
        rol: str = payload.get("rol")
        nombre: str = payload.get("nombre_completo") or payload.get("nombre")
        usuario_id: str = payload.get("id") or email  # ⚠️ Agregamos el id para que el endpoint de la IA no falle al hacer usuario_actual.get("id")
        
        if email is None or rol is None:
            raise credenciales_exception
            
        # Retornamos el diccionario completo con lo que tu endpoint de la IA necesita
        return {
            "id": usuario_id, 
            "email": email, 
            "rol": rol, 
            "nombre_completo": nombre
        }
        
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        # PyJWT maneja estas excepciones específicas para firmas expiradas o tokens alterados
        raise credenciales_exception