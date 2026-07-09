from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_occupancy_router_esta_montado_y_responde():
    """
    Regresión del bug donde ocupacion_router se importaba en main.py pero
    nunca se incluía con app.include_router(...), dejando /api/occupancy/*
    inalcanzable (404) sin que ningún test lo detectara.
    """
    response = client.get("/api/occupancy/spaces")

    assert response.status_code == 200
    assert response.json()["ok"] is True
