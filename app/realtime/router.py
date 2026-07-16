from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime.manager import realtime_manager

router = APIRouter(prefix="/realtime", tags=["Realtime"])


@router.websocket("/ws")
async def websocket_realtime(websocket: WebSocket):
    await realtime_manager.conectar(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime_manager.desconectar(websocket)
    except Exception:
        realtime_manager.desconectar(websocket)