import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:axis2026@localhost:27017/axis_db?authSource=admin")

async def poblar_base_datos():
    print("⏳ Conectando a MongoDB para la siembra masiva...")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client.get_default_database()
    
    # 1. Limpiamos la colección para no duplicar datos
    await db["espacios"].delete_many({})
    print("🧹 Colección 'espacios' limpiada.")
    
    # 2. Preparamos el bloque masivo de aulas (5 edificios, mínimo 3 espacios cada uno)
    espacios_seed = [
        # ==========================================
        # EDIFICIO 1: Edificio de las A (Real)
        # ==========================================
        {
            "nombre": "Aula EA39A2-1",
            "bloque": "edificio_a", 
            "tipo": "aula",
            "capacidad": 35,
            "equipamiento": ["Pizarra", "Proyector", "Sillas universitarias"],
            "estado_actual": "disponible",
            "coordenadas_gps": "-0.198362, -78.503849",
            "svg_id": "EA39A2-1" 
        },
        {
            "nombre": "Aula EA39A2-2",
            "bloque": "edificio_a", 
            "tipo": "aula",
            "capacidad": 35,
            "equipamiento": ["Pizarra", "Proyector"],
            "estado_actual": "ocupado",
            "coordenadas_gps": "-0.198362, -78.503849",
            "svg_id": "EA39A2-2" 
        },
        {
            "nombre": "Aula EA39A2-3",
            "bloque": "edificio_a", 
            "tipo": "aula",
            "capacidad": 30,
            "equipamiento": ["Pizarra inteligente"],
            "estado_actual": "mantenimiento",
            "coordenadas_gps": "-0.198362, -78.503849",
            "svg_id": "EA39A2-3" 
        },
        {
            "nombre": "Aula EA39A3-1",
            "bloque": "edificio_a", 
            "tipo": "aula",
            "capacidad": 40,
            "equipamiento": ["Pizarra", "Proyector"],
            "estado_actual": "disponible",
            "coordenadas_gps": "-0.198362, -78.503849",
            "svg_id": "EA39A3-1" 
        },

        # ==========================================
        # EDIFICIO 2: Edificio de los Laboratorios (Real)
        # ==========================================
        {
            "nombre": "Laboratorio de Ciencias 1",
            "bloque": "edificio_labs",
            "tipo": "laboratorio",
            "capacidad": 25,
            "equipamiento": ["Mesas de acero", "Microscopios", "Lavabos"],
            "estado_actual": "ocupado",
            "coordenadas_gps": "-0.198633, -78.503015",
            "svg_id": "LABCIENCIAS1"
        },
        {
            "nombre": "Laboratorio de Ciencias 2",
            "bloque": "edificio_labs",
            "tipo": "laboratorio",
            "capacidad": 25,
            "equipamiento": ["Reactivos", "Campana extractora"],
            "estado_actual": "disponible",
            "coordenadas_gps": "-0.198633, -78.503015",
            "svg_id": "LABCIENCIAS2"
        },
        {
            "nombre": "Laboratorio de Ciencias 3",
            "bloque": "edificio_labs",
            "tipo": "laboratorio",
            "capacidad": 20,
            "equipamiento": ["Mesas de acero", "Equipos de medición"],
            "estado_actual": "mantenimiento",
            "coordenadas_gps": "-0.198633, -78.503015",
            "svg_id": "LABCIENCIAS3"
        },

        # ==========================================
        # EDIFICIO 3: Facultad de Ingeniería (Contextual)
        # ==========================================
        {
            "nombre": "Laboratorio de Sistemas",
            "bloque": "fac_ingenieria",
            "tipo": "laboratorio",
            "capacidad": 30,
            "equipamiento": ["30 PCs", "Servidor Local", "Aire Acondicionado"],
            "estado_actual": "ocupado",
            "coordenadas_gps": "-0.197600, -78.501500",
            "svg_id": "lab_sistemas"
        },
        {
            "nombre": "Aula Magna de Ingeniería",
            "bloque": "fac_ingenieria",
            "tipo": "auditorio",
            "capacidad": 100,
            "equipamiento": ["Sistema de Audio", "Proyector 4K", "Micrófonos"],
            "estado_actual": "disponible",
            "coordenadas_gps": "-0.197600, -78.501500",
            "svg_id": "aula_magna_ing"
        },
        {
            "nombre": "Aula de Dibujo Civil",
            "bloque": "fac_ingenieria",
            "tipo": "aula",
            "capacidad": 40,
            "equipamiento": ["Mesas de dibujo técnico"],
            "estado_actual": "disponible",
            "coordenadas_gps": "-0.197600, -78.501500",
            "svg_id": "aula_dibujo"
        },

        # ==========================================
        # EDIFICIO 4: Biblioteca Central UCE (Contextual)
        # ==========================================
        {
            "nombre": "Sala de Lectura Principal",
            "bloque": "bib_central",
            "tipo": "biblioteca",
            "capacidad": 80,
            "equipamiento": ["Mesas compartidas", "Wi-Fi 6", "Lámparas de lectura"],
            "estado_actual": "disponible",
            "coordenadas_gps": "-0.201100, -78.503500",
            "svg_id": "sala_lectura_1"
        },
        {
            "nombre": "Hemeroteca Histórica",
            "bloque": "bib_central",
            "tipo": "biblioteca",
            "capacidad": 20,
            "equipamiento": ["Archiveros", "Mesas individuales"],
            "estado_actual": "mantenimiento",
            "coordenadas_gps": "-0.201100, -78.503500",
            "svg_id": "hemeroteca"
        },
        {
            "nombre": "Sala de Cómputo",
            "bloque": "bib_central",
            "tipo": "laboratorio",
            "capacidad": 40,
            "equipamiento": ["40 PCs de consulta", "Impresoras"],
            "estado_actual": "ocupado",
            "coordenadas_gps": "-0.201100, -78.503500",
            "svg_id": "compu_biblioteca"
        },

        # ==========================================
        # EDIFICIO 5: Facultad de Ciencias Administrativas (Contextual)
        # ==========================================
        {
            "nombre": "Aula 201 - Contabilidad",
            "bloque": "fac_administrativas",
            "tipo": "aula",
            "capacidad": 45,
            "equipamiento": ["Pizarra", "Proyector"],
            "estado_actual": "disponible",
            "coordenadas_gps": "-0.199500, -78.502800",
            "svg_id": "aula_201_adm"
        },
        {
            "nombre": "Aula 202 - Auditoría",
            "bloque": "fac_administrativas",
            "tipo": "aula",
            "capacidad": 45,
            "equipamiento": ["Pizarra", "TV LED"],
            "estado_actual": "disponible",
            "coordenadas_gps": "-0.199500, -78.502800",
            "svg_id": "aula_202_adm"
        },
        {
            "nombre": "Sala de Reuniones y Casos",
            "bloque": "fac_administrativas",
            "tipo": "aula",
            "capacidad": 15,
            "equipamiento": ["Mesa redonda", "Pantalla interactiva"],
            "estado_actual": "ocupado",
            "coordenadas_gps": "-0.199500, -78.502800",
            "svg_id": "sala_casos"
        }
    ]
    
    # 3. Insertamos masivamente en la base de datos
    await db["espacios"].insert_many(espacios_seed)
    print(f"✅ ¡Siembra exitosa! Se insertaron {len(espacios_seed)} espacios distribuidos en 5 edificios.")

if __name__ == "__main__":
    asyncio.run(poblar_base_datos())