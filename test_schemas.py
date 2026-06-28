import json
from schemas import EspacioCreate
from pydantic import ValidationError

print("--- 🧪 INICIANDO PRUEBAS DE PYDANTIC (V2) ---")

# CASO 1: Datos válidos (Debería funcionar perfectamente)
datos_validos = {
    "nombre": "Laboratorio de Computación 3",
    "bloque": "Bloque B",
    "tipo": "laboratorio",
    "capacidad": 30,
    "equipamiento": ["30 PCs", "Proyector"]
}

try:
    espacio_ok = EspacioCreate(**datos_validos)
    print("\n✅ CASO 1 EXITOSO: Los datos son válidos.")
    
    # En Pydantic V2 usamos model_dump() para obtener un diccionario de Python
    dict_datos = espacio_ok.model_dump()
    # Usamos el módulo nativo json de Python para imprimirlo ordenadamente con indentación
    print(f"Objeto creado de forma segura:\n{json.dumps(dict_datos, indent=2, ensure_ascii=False)}")
    
except ValidationError as e:
    print("\n❌ CASO 1 FALLÓ (No debería fallar):")
    print(e.json())

print("\n-------------------------------------------")

# CASO 2: Datos inválidos (Pydantic debería detectar los errores)
datos_invalidos = {
    "nombre": "Aula 101",
    "bloque": "Bloque A",
    "tipo": "oficina",      # ❌ ERROR: Solo se permite "aula" o "laboratorio"
    "capacidad": -5,        # ❌ ERROR: Debe ser mayor a 0 (gt=0)
    "equipamiento": []
}

try:
    print("\n⏳ Intentando validar datos incorrectos...")
    espacio_error = EspacioCreate(**datos_invalidos)
except ValidationError as e:
    print("\n🛡️ CASO 2 EXITOSO: Pydantic detuvo los datos inválidos correctamente.")
    print(f"Errores detectados por el 'aduanero' ({e.error_count()} errores):")
    
    # Formato compatible con Pydantic V2 para leer los errores detallados
    for error in e.errors():
        campo = error['loc'][0]
        mensaje = error['msg']
        print(f"  • Campo [{campo}]: {mensaje}")