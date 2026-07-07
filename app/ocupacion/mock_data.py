# Datos simulados de ocupación (Fase 1).
# Reemplazar por lecturas reales del servicio de visión artificial en fases futuras.
# El campo "status" NO se define aquí: se calcula en el service a partir de
# occupancyPercent, para que la regla de negocio viva en un solo lugar.

RAW_SPACES = [
    {
        "id": "biblioteca-fica",
        "name": "Biblioteca FICA",
        "description": "Biblioteca de la Facultad de Ingeniería, Ciencias Físicas y Matemática.",
        "type": "library",
        "building": "Facultad de Ingeniería",
        "floor": "Planta Baja",
        "totalSeats": 40,
        "occupiedSeats": 18,
        "freeSeats": 22,
        "computersTotal": 12,
        "computersAvailable": 5,
        "studyRoomsTotal": 3,
        "studyRoomsAvailable": 2,
        "distanceMinutes": 5,
        "occupancyPercent": 45,
    },
    {
        "id": "biblioteca-general",
        "name": "Biblioteca General",
        "description": "Biblioteca principal del Campus Central de la UCE.",
        "type": "library",
        "building": "Campus Central",
        "floor": "Planta 1",
        "totalSeats": 120,
        "occupiedSeats": 98,
        "freeSeats": 22,
        "computersTotal": 30,
        "computersAvailable": 4,
        "studyRoomsTotal": 8,
        "studyRoomsAvailable": 1,
        "distanceMinutes": 9,
        "occupancyPercent": 82,
    },
    {
        "id": "sala-grupal-2",
        "name": "Sala Grupal 2",
        "description": "Sala de estudio grupal en el Edificio A.",
        "type": "study_room",
        "building": "Edificio A",
        "floor": "Planta 1",
        "totalSeats": 8,
        "occupiedSeats": 2,
        "freeSeats": 6,
        "computersTotal": 0,
        "computersAvailable": 0,
        "studyRoomsTotal": 1,
        "studyRoomsAvailable": 1,
        "distanceMinutes": 3,
        "occupancyPercent": 25,
    },
    {
        "id": "laboratorio-computadoras",
        "name": "Laboratorio de Computadoras",
        "description": "Laboratorio de cómputo del Edificio Tecnológico.",
        "type": "computer_lab",
        "building": "Edificio Tecnológico",
        "floor": "Planta 2",
        "totalSeats": 30,
        "occupiedSeats": 29,
        "freeSeats": 1,
        "computersTotal": 30,
        "computersAvailable": 1,
        "studyRoomsTotal": 0,
        "studyRoomsAvailable": 0,
        "distanceMinutes": 7,
        "occupancyPercent": 97,
    },
    {
        "id": "sala-lectura-humanidades",
        "name": "Sala de Lectura Humanidades",
        "description": "Sala de lectura de la Facultad de Filosofía, Letras y Ciencias de la Educación.",
        "type": "study_room",
        "building": "Facultad de Filosofía",
        "floor": "Planta Baja",
        "totalSeats": 24,
        "occupiedSeats": 0,
        "freeSeats": 0,
        "computersTotal": 0,
        "computersAvailable": 0,
        "studyRoomsTotal": 2,
        "studyRoomsAvailable": 0,
        "distanceMinutes": 12,
        "occupancyPercent": None,
    },
]

# Mapea cada espacio a la imagen/video de prueba que el vision-service debe
# analizar (Fase 2). Las rutas son relativas a la raíz de vision-service/.
# Si el archivo no existe, el vision-service responde con datos simulados
# (source: "vision-service-fallback") en vez de fallar.
SPACE_VISION_SOURCES = {
    "biblioteca-fica": {
        "sourceType": "sample_image",
        "sourcePath": "samples/BIBLIO1.jpg",
    },
    "biblioteca-general": {
        "sourceType": "sample_image",
        "sourcePath": "samples/biblioteca_general.jpg",
    },
    "sala-grupal-2": {
        "sourceType": "sample_image",
        "sourcePath": "samples/sala_grupal_2.jpg",
    },
    "laboratorio-computadoras": {
        "sourceType": "sample_image",
        "sourcePath": "samples/laboratorio_computadoras.jpg",
    },
    "sala-lectura-humanidades": {
        "sourceType": "sample_image",
        "sourcePath": "samples/sala_lectura_humanidades.jpg",
    },
}
