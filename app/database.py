import os
from motor.motor_asyncio import AsyncIOMotorClient

# Obtenemos la URI de conexión de las variables de entorno
MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:axis2026@localhost:27017/axis_db?authSource=admin")

# Inicializamos el cliente asíncrono
client = AsyncIOMotorClient(MONGO_URI)

# Apuntamos a la base de datos
db = client.get_default_database()

# Función utilitaria para verificar la conexión
async def verificar_conexion():
    try:
        # El comando ping evalúa si la base de datos responde
        await client.admin.command('ping')
        print("¡Conexión exitosa a MongoDB!")
    except Exception as e:
        print(f"Error al conectar a MongoDB: {e}")