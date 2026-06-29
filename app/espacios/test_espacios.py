import pytest
from pydantic import ValidationError
from app.espacios.schemas import EspacioCreate

def test_crear_espacio_valido():
    datos = {
        "nombre": "Laboratorio de Computación 3",
        "bloque": "Bloque B",
        "tipo": "laboratorio",
        "capacidad": 30
    }
    espacio = EspacioCreate(**datos)
    assert espacio.nombre == "Laboratorio de Computación 3"
    assert espacio.estado_actual == "disponible"  
    assert espacio.equipamiento == []          

def test_crear_espacio_tipo_invalido():
    datos = {
        "nombre": "Aula 101",
        "bloque": "Bloque A",
        "tipo": "discoteca", 
        "capacidad": 20
    }
    with pytest.raises(ValidationError) as exc_info:
        EspacioCreate(**datos)
    assert "tipo" in str(exc_info.value)

def test_crear_espacio_capacidad_invalida():
    datos = {
        "nombre": "Aula 101",
        "bloque": "Bloque A",
        "tipo": "aula",
        "capacidad": 0 
    }
    with pytest.raises(ValidationError):
        EspacioCreate(**datos)
