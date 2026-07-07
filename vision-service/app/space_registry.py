# Registro estático de espacios que el scheduler debe analizar (Fase 3).
#
# El vision-service ahora analiza en segundo plano sin esperar a que el
# backend le pida un espacio puntual, así que necesita conocer por sí mismo
# la lista completa de espacios y su imagen/video asociado. Esto duplica a
# propósito una porción pequeña de lo que ya sabe el backend principal
# (app/ocupacion/mock_data.py) — sin base de datos ni registro compartido
# todavía, es la forma más simple de que ambos servicios queden desacoplados.
# Unificar esta fuente de verdad queda pendiente para una fase futura.

SPACE_REGISTRY = [
    {
        "spaceId": "biblioteca-fica",
        "spaceName": "Biblioteca FICA",
        "totalSeats": 40,
        "computersTotal": 12,
        "sourceType": "sample_image",
        "sourcePath": "samples/BIBLIO1.jpg",
    },
    {
        "spaceId": "biblioteca-general",
        "spaceName": "Biblioteca General",
        "totalSeats": 120,
        "computersTotal": 30,
        "sourceType": "sample_image",
        "sourcePath": "samples/biblioteca_general.jpg",
    },
    {
        "spaceId": "sala-grupal-2",
        "spaceName": "Sala Grupal 2",
        "totalSeats": 8,
        "computersTotal": 0,
        "sourceType": "sample_image",
        "sourcePath": "samples/sala_grupal_2.jpg",
    },
    {
        "spaceId": "laboratorio-computadoras",
        "spaceName": "Laboratorio de Computadoras",
        "totalSeats": 30,
        "computersTotal": 30,
        "sourceType": "sample_image",
        "sourcePath": "samples/laboratorio_computadoras.jpg",
    },
    {
        "spaceId": "sala-lectura-humanidades",
        "spaceName": "Sala de Lectura Humanidades",
        "totalSeats": 24,
        "computersTotal": 0,
        "sourceType": "sample_image",
        "sourcePath": "samples/sala_lectura_humanidades.jpg",
    },
]
