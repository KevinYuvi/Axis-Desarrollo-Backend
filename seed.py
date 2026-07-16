import asyncio
import os
import sys
from datetime import datetime

# En consolas Windows (cp1252) los emojis de los prints rompen el script;
# forzamos UTF-8 en la salida estándar cuando sea posible.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Cargar .env ANTES de leer MONGO_URI, igual que hace main.py,
# para que la conexión apunte al mismo entorno que la API.
from dotenv import load_dotenv

load_dotenv()

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:axis2026@localhost:27017/axis_db?authSource=admin")

async def poblar_base_datos():
    print("⏳ Conectando a MongoDB para la siembra masiva integral...")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client.get_default_database()

    # 1. Limpiamos la colección para evitar colisiones
    existentes = await db["espacios"].count_documents({})
    print(f"Documentos existentes en 'espacios' antes de limpiar: {existentes}")
    await db["reservas"].delete_many({})
    await db["reportes"].delete_many({})
    await db["espacios"].delete_many({})
    print("🧹 Colección 'espacios' limpiada por completo.")
    
    espacios_seed = []

    # =========================================================================
    # EDIFICIO 1: Edificio de las A (REAL)
    # =========================================================================
    coordenadas_a = "-0.198285, -78.503981"
    
    # Piso 1
    aulas_piso1_a = ["EA39A1-1", "EA39A1-2", "EA39A1-3", "EA39A1-4", "EA39A1-5", "EA39A1-6", "EA39A1-7", "EA39A1-8"]
    for i, aula_id in enumerate(aulas_piso1_a):
        estado = "disponible" if i % 3 == 0 else ("ocupado" if i % 3 == 1 else "mantenimiento")
        espacios_seed.append({
            "nombre": f"Aula {aula_id}",
            "bloque": "edificio_a",
            "tipo": "aula",
            "capacidad": 35 if i % 2 == 0 else 40,
            "equipamiento": ["Proyector", "Pizarra", "Sillas Universitarias"] if i % 2 == 0 else ["Pizarra Inteligente", "Sistema de Audio"],
            "estado_actual": estado,
            "coordenadas_gps": coordenadas_a,
            "svg_id": aula_id
        })

    # Piso 2
    aulas_piso2_a = ["EA39A2-1", "EA39A2-2", "EA39A2-3", "EA39A2-4", "EA39A2-5", "EA39A2-6", "EA39A2-7", "EA39A2-8"]
    for i, aula_id in enumerate(aulas_piso2_a):
        estado = "disponible" if i % 3 == 1 else ("ocupado" if i % 3 == 2 else "mantenimiento")
        espacios_seed.append({
            "nombre": f"Aula {aula_id}",
            "bloque": "edificio_a",
            "tipo": "aula",
            "capacidad": 30 if i % 2 == 0 else 45,
            "equipamiento": ["Proyector", "Pizarra"] if i % 2 == 0 else ["Televisor LED 65", "Pizarra", "Wi-Fi dedicado"],
            "estado_actual": estado,
            "coordenadas_gps": coordenadas_a,
            "svg_id": aula_id
        })

    # =========================================================================
    # EDIFICIO 2: Edificio de los Laboratorios (REAL)
    # =========================================================================
    coordenadas_labs = "-0.198649, -78.503011"
    
    # Piso 1
    labs_piso1 = ["LAB1", "LAB2", "LAB3", "LAB4", "LAB5", "LAB6", "LAB7", "LAB8"]
    for i, lab_id in enumerate(labs_piso1):
        estado = "disponible" if i % 2 == 0 else "ocupado"
        espacios_seed.append({
            "nombre": f"Laboratorio {lab_id}",
            "bloque": "edificio_labs",
            "tipo": "laboratorio",
            "capacidad": 25,
            "equipamiento": ["25 PCs de escritorio", "Proyector", "Pizarra"],
            "estado_actual": estado,
            "coordenadas_gps": coordenadas_labs,
            "svg_id": lab_id
        })

    # Piso 3
    labs_piso3 = ["LABCIENCIAS1", "LABCIENCIAS2", "LABCIENCIAS3", "LABCIENCIAS4", "LABCIENCIAS5", "LABCIENCIAS6", "LABCIENCIAS7", "LABCIENCIAS8"]
    for i, lab_id in enumerate(labs_piso3):
        estado = "ocupado" if i % 3 == 0 else ("mantenimiento" if i % 3 == 1 else "disponible")
        espacios_seed.append({
            "nombre": f"Laboratorio {lab_id}",
            "bloque": "edificio_labs",
            "tipo": "laboratorio",
            "capacidad": 20 if i % 2 == 0 else 30,
            "equipamiento": ["Instrumental de Ciencias", "Extractores", "Mesas de Acero"] if i % 2 == 0 else ["Computadoras core i7", "Módulos de desarrollo"],
            "estado_actual": estado,
            "coordenadas_gps": coordenadas_labs,
            "svg_id": lab_id
        })

    # =========================================================================
    # EDIFICIO 3: Facultad de Ingeniería (FICTICIO - CONTEXTO)
    # =========================================================================
    espacios_seed.extend([
        {
            "nombre": "Laboratorio de Sistemas", "bloque": "fac_ingenieria", "tipo": "laboratorio", "capacidad": 30,
            "equipamiento": ["30 PCs", "Servidor Local"], "estado_actual": "ocupado",
            "coordenadas_gps": "-0.197600, -78.501500", "svg_id": "lab_sistemas"
        },
        {
            "nombre": "Aula Magna de Ingeniería", "bloque": "fac_ingenieria", "tipo": "auditorio", "capacidad": 100,
            "equipamiento": ["Sistema de Audio", "Proyector 4K"], "estado_actual": "disponible",
            "coordenadas_gps": "-0.197600, -78.501500", "svg_id": "aula_magna_ing"
        },
        {
            "nombre": "Aula de Dibujo Civil", "bloque": "fac_ingenieria", "tipo": "aula", "capacidad": 40,
            "equipamiento": ["Mesas de dibujo técnico"], "estado_actual": "disponible",
            "coordenadas_gps": "-0.197600, -78.501500", "svg_id": "aula_dibujo"
        }
    ])

    # =========================================================================
    # EDIFICIO 4: Biblioteca Central UCE (FICTICIO - CONTEXTO)
    # =========================================================================
    espacios_seed.extend([
        {
            "nombre": "Sala de Lectura Principal", "bloque": "bib_central", "tipo": "biblioteca", "capacidad": 80,
            "equipamiento": ["Mesas compartidas", "Wi-Fi 6"], "estado_actual": "disponible",
            "coordenadas_gps": "-0.201100, -78.503500", "svg_id": "sala_lectura_1"
        },
        {
            "nombre": "Hemeroteca Histórica", "bloque": "bib_central", "tipo": "biblioteca", "capacidad": 20,
            "equipamiento": ["Archiveros", "Mesas individuales"], "estado_actual": "mantenimiento",
            "coordenadas_gps": "-0.201100, -78.503500", "svg_id": "hemeroteca"
        },
        {
            "nombre": "Sala de Cómputo", "bloque": "bib_central", "tipo": "laboratorio", "capacidad": 40,
            "equipamiento": ["40 PCs de consulta", "Impresoras"], "estado_actual": "ocupado",
            "coordenadas_gps": "-0.201100, -78.503500", "svg_id": "compu_biblioteca"
        }
    ])

    # =========================================================================
    # EDIFICIO 5: Facultad de C. Administrativas (FICTICIO - CONTEXTO)
    # =========================================================================
    espacios_seed.extend([
        {
            "nombre": "Aula 201 - Contabilidad", "bloque": "fac_administrativas", "tipo": "aula", "capacidad": 45,
            "equipamiento": ["Pizarra", "Proyector"], "estado_actual": "disponible",
            "coordenadas_gps": "-0.199500, -78.502800", "svg_id": "aula_201_adm"
        },
        {
            "nombre": "Aula 202 - Auditoría", "bloque": "fac_administrativas", "tipo": "aula", "capacidad": 45,
            "equipamiento": ["Pizarra", "TV LED"], "estado_actual": "disponible",
            "coordenadas_gps": "-0.199500, -78.502800", "svg_id": "aula_202_adm"
        },
        {
            "nombre": "Sala de Reuniones y Casos", "bloque": "fac_administrativas", "tipo": "aula", "capacidad": 15,
            "equipamiento": ["Mesa redonda", "Pantalla interactiva"], "estado_actual": "ocupado",
            "coordenadas_gps": "-0.199500, -78.502800", "svg_id": "sala_casos"
        }
    ])

    # =========================================================================
    # EDIFICIO 6: Bibliotecas (REAL) — conectan el módulo de ocupación
    # (vision-service) con la BD académica: el svg_id coincide con el id del
    # espacio monitoreado por cámara (p. ej. "biblioteca-cisco").
    # =========================================================================
    espacios_seed.extend([
        {
            # Biblioteca Cisco de la Universidad Central: único espacio con
            # cámara IP conectada; su svg_id enlaza con el módulo de ocupación.
            "nombre": "Biblioteca Cisco", "bloque": "edificio_a", "tipo": "biblioteca", "capacidad": 60,
            "equipamiento": ["Mesas de estudio", "Wi-Fi", "Estanterías abiertas", "10 PCs de consulta"],
            "estado_actual": "disponible",
            "coordenadas_gps": "-0.198310, -78.503950", "svg_id": "biblioteca-cisco"
        },
        {
            "nombre": "Sala de Estudio Grupal FICA", "bloque": "edificio_a", "tipo": "biblioteca", "capacidad": 24,
            "equipamiento": ["Mesas grupales", "Pizarra", "Wi-Fi"],
            "estado_actual": "disponible",
            "coordenadas_gps": "-0.198330, -78.503920", "svg_id": "sala-estudio-fica"
        },
        {
            "nombre": "Sala de Lectura Silenciosa FICA", "bloque": "edificio_a", "tipo": "biblioteca", "capacidad": 30,
            "equipamiento": ["Cubículos individuales", "Lámparas de escritorio", "Wi-Fi"],
            "estado_actual": "ocupado",
            "coordenadas_gps": "-0.198350, -78.503900", "svg_id": "sala-lectura-fica"
        }
    ])

    # 3. Inserción masiva
    resultado = await db["espacios"].insert_many(espacios_seed)
    print(f"¡Siembra completada con éxito!")
    print(f"Se registraron un total de {len(resultado.inserted_ids)} espacios en la base de datos distribuidos en 6 edificios.")

    # 4. Datos académicos base.
    # Estos datos ya no están quemados en el service.py: quedan en MongoDB y
    # pueden reemplazarse por formularios administrativos más adelante.
    await db["edificios"].delete_many({})
    await db["grupos"].delete_many({})
    await db["horarios_estudiantes"].delete_many({})
    await db["estudiante_grupos"].delete_many({})

    edificios_academicos = [
        {
            "id": "edificio-a",
            "nombre": "Edificio A",
            "bloque": "edificio_a",
            "referencia": "Edificio de aulas A, junto al ingreso principal.",
            "latitude": -0.198285,
            "longitude": -78.503981,
        },
        {
            "id": "edificio-labs",
            "nombre": "Edificio de Laboratorios",
            "bloque": "edificio_labs",
            "referencia": "Zona de laboratorios académicos.",
            "latitude": -0.198649,
            "longitude": -78.503011,
        },
    ]

    await db["edificios"].insert_many(edificios_academicos)

    grupo = {
        "id": "grupo-sexto-a",
        "nombre": "Sexto A",
        "carrera": "Desarrollo de Software",
        "nivel": "Sexto",
        "activo": True,
    }

    await db["grupos"].insert_one(grupo)

    horarios_estudiantes = []
    dias_academicos = ["lunes", "martes", "miercoles", "jueves", "viernes"]

    for dia in dias_academicos:
        horarios_estudiantes.extend([
            {
                "grupo_id": "grupo-sexto-a",
                "materia": "Programación II",
                "docente": "Ing. Carlos Pérez",
                "aula": "Aula EA39A1-1",
                "edificio_id": "edificio-a",
                "dia_semana": dia,
                "hora_inicio": "08:00",
                "hora_fin": "10:00",
                "activo": True,
            },
            {
                "grupo_id": "grupo-sexto-a",
                "materia": "Base de Datos",
                "docente": "Ing. María López",
                "aula": "Laboratorio LAB2",
                "edificio_id": "edificio-labs",
                "dia_semana": dia,
                "hora_inicio": "10:00",
                "hora_fin": "12:00",
                "activo": True,
            },
            {
                "grupo_id": "grupo-sexto-a",
                "materia": "Ingeniería de Software",
                "docente": "Ing. Ana Zambrano",
                "aula": "Aula EA39A2-2",
                "edificio_id": "edificio-a",
                "dia_semana": dia,
                "hora_inicio": "14:00",
                "hora_fin": "16:00",
                "activo": True,
            },
        ])
    await db["horarios_estudiantes"].insert_many(horarios_estudiantes)

    await db["estudiante_grupos"].insert_one({
        "usuario_id": "mock-estudiante-id",
        "email": "estudiante@uce.edu.ec",
        "grupo_id": "grupo-sexto-a",
        "grupo_nombre": "Sexto A",
        "activo": True,
        "asignado_por": "seed",
        "fecha_asignacion": datetime.utcnow(),
    })

    print("✅ Datos académicos base creados: edificios, grupo, horarios y asignación de prueba.")

if __name__ == "__main__":
    asyncio.run(poblar_base_datos())