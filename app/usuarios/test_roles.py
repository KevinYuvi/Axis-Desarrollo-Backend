from app.usuarios.utils import normalizar_rol
from app.usuarios.schemas import RoleEnum


def test_normalizar_alias():
    assert normalizar_rol("Profesor") == "docente"
    assert normalizar_rol("Docente") == "docente"
    assert normalizar_rol("gestor") == "admin"
    assert normalizar_rol("Admin") == "admin"
    assert normalizar_rol("Ayudante") == "ayudante"
    assert normalizar_rol(None) == "estudiante"
    assert normalizar_rol("cualquier_cosa") == "estudiante"


def test_role_enum_incluye_ayudante():
    assert RoleEnum.AYUDANTE.value == "Ayudante"
