from pydantic import BaseModel, EmailStr, Field
from enum import Enum
from typing import Optional

class RoleEnum(str, Enum):
    ADMIN = "Admin"
    DOCENTE = "Docente"
    ESTUDIANTE = "Estudiante"
    AYUDANTE = "Ayudante"

class UserCreate(BaseModel):
    email: EmailStr
    nombre_completo: str
    password: str = Field(..., min_length=6, description="La contraseña debe tener al menos 6 caracteres")
    rol: RoleEnum = RoleEnum.ESTUDIANTE # Rol por defecto

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    nombre_completo: str
    rol: RoleEnum

    class Config:
        from_attributes = True