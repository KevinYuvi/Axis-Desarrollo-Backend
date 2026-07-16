from app import config

# Registro de espacios que el scheduler analiza con la cámara IP.
# "biblioteca-cisco" es la Biblioteca Cisco de la Universidad Central: su
# spaceId debe coincidir con STATIC_SPACE_METADATA (backend) y con
# LIVE_CAMERA_SPACE_ID (frontend) para que todo el flujo use el mismo espacio.
SPACE_REGISTRY = [
    {
        "spaceId": "biblioteca-cisco",
        "spaceName": "Biblioteca Cisco",
        "totalSeats": 40,
        "computersTotal": 12,
        "sourceType": "ip_camera_snapshot",
        "sourcePath": config.IP_CAMERA_SNAPSHOT_URL,
    },
]