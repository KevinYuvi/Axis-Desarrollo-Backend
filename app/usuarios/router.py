from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.usuarios.schemas import UserCreate, UserResponse
from app.usuarios.utils import (
    hash_password,
    verificar_password,
    crear_token_acceso,
    requerir_roles,
    normalizar_rol,
    ROLES_CANONICOS,
    ALIAS_ROLES,
)
from app.usuarios.clerk_api import listar_usuarios_clerk, asignar_rol_clerk
from app.database import db

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

coleccion_usuarios = db["usuarios"]

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def registrar_usuario(usuario: UserCreate):
    # 1. Verificar si el correo ya existe en la base de datos
    usuario_existente = await coleccion_usuarios.find_one({"email": usuario.email})
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya está registrado"
        )
    
    # 2. Convertir el esquema de Pydantic a diccionario de Python
    datos_usuario = usuario.model_dump()
    
    # 3. Encriptar la contraseña antes de guardarla (Seguridad Obligatoria)
    datos_usuario["password"] = hash_password(datos_usuario["password"])
    
    # 4. Insertar el documento en la colección de MongoDB
    resultado = await coleccion_usuarios.insert_one(datos_usuario)
    
    # 5. Recuperar el usuario guardado para retornar la respuesta armada
    nuevo_usuario = await coleccion_usuarios.find_one({"_id": resultado.inserted_id})
    if not nuevo_usuario:
        raise HTTPException(status_code=500, detail="Error al registrar el usuario")
        
    # Mapear el ObjectId de Mongo al campo "id" que espera el UserResponse
    nuevo_usuario["id"] = str(nuevo_usuario["_id"])
    return nuevo_usuario


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # form_data.username se mapeará automáticamente al campo de texto que usemos como email
    usuario = await coleccion_usuarios.find_one({"email": form_data.username})
    
    # Verificar existencia de usuario y validar contraseña
    if not usuario or not verificar_password(form_data.password, usuario["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de acceso incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Creamos el payload con los datos que queremos almacenar dentro del JWT
    payload = {
        "id": str(usuario["_id"]),
        "sub": usuario["email"],
        "rol": usuario["rol"],
        "nombre": usuario["nombre_completo"],
    }
    
    # Generamos el token de acceso
    token = crear_token_acceso(data=payload)
    
    # Retornamos la estructura estándar que exige OAuth2
    return {"access_token": token, "token_type": "bearer"}


@router.get("/", summary="Listar usuarios (solo Gestor)")
async def listar_usuarios(_: dict = Depends(requerir_roles("Admin"))):
    """Devuelve los usuarios registrados en Clerk con su id, email y rol actual."""
    return await listar_usuarios_clerk()


@router.patch("/{user_id}/rol", summary="Asignar rol a un usuario (solo Gestor)")
async def cambiar_rol(user_id: str, nuevo_rol: str,
                      _: dict = Depends(requerir_roles("Admin"))):
    """Fija public_metadata.rol del usuario en Clerk (roles canónicos o alias aceptados)."""
    rol = normalizar_rol(nuevo_rol)
    if nuevo_rol.strip().lower() not in ROLES_CANONICOS and nuevo_rol.strip().lower() not in ALIAS_ROLES:
        raise HTTPException(status_code=422,
                            detail=f"Rol inválido: {nuevo_rol}. Válidos: {sorted(ROLES_CANONICOS)}")
    return await asignar_rol_clerk(user_id, rol)