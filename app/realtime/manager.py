from fastapi import WebSocket
from typing import List


class RealtimeManager:
    def __init__(self):
        self.conexiones_activas: List[WebSocket] = []

    async def conectar(self, websocket: WebSocket):
        await websocket.accept()
        self.conexiones_activas.append(websocket)

    def desconectar(self, websocket: WebSocket):
        if websocket in self.conexiones_activas:
            self.conexiones_activas.remove(websocket)

    async def emitir(self, evento: dict):
        conexiones_muertas = []

        for conexion in self.conexiones_activas:
            try:
                await conexion.send_json(evento)
            except Exception:
                conexiones_muertas.append(conexion)

        for conexion in conexiones_muertas:
            self.desconectar(conexion)


realtime_manager = RealtimeManager()