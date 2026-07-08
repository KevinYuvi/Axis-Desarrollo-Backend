import httpx
import pytest

from app import detector, occupancy_calculator
from app.schemas import AnalyzeRequest

FAKE_SNAPSHOT_URL = "http://192.168.100.99:8080/shot.jpg"


@pytest.fixture(autouse=True)
def stub_yolo_model_disponible(monkeypatch):
    """
    Simula que el modelo YOLO ya está cargado, sin descargar pesos reales,
    para poder probar solo la lógica de captura/decodificación por HTTP.
    """
    monkeypatch.setattr(detector, "_load_yolo_model", lambda: object())


def test_count_people_in_ip_camera_snapshot_devuelve_none_si_falla_la_peticion(monkeypatch):
    def fake_get(url, timeout):
        raise httpx.ConnectError("no se pudo conectar", request=None)

    monkeypatch.setattr(httpx, "get", fake_get)

    assert detector.count_people_in_ip_camera_snapshot(FAKE_SNAPSHOT_URL) is None


def test_count_people_in_ip_camera_snapshot_devuelve_none_si_la_imagen_no_se_puede_decodificar(monkeypatch):
    class FakeResponse:
        content = b"esto-no-es-un-jpeg-valido"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(httpx, "get", lambda url, timeout: FakeResponse())

    assert detector.count_people_in_ip_camera_snapshot(FAKE_SNAPSHOT_URL) is None


IP_CAMERA_REQUEST = AnalyzeRequest(
    spaceId="biblioteca-fica",
    spaceName="Biblioteca FICA",
    totalSeats=40,
    computersTotal=12,
    sourceType="ip_camera_snapshot",
    sourcePath=FAKE_SNAPSHOT_URL,
)


def test_analyze_space_cae_a_fallback_si_la_camara_ip_no_responde(monkeypatch):
    monkeypatch.setattr(detector, "count_people_in_ip_camera_snapshot", lambda url: None)

    result = occupancy_calculator.analyze_space(IP_CAMERA_REQUEST)

    assert result.source == "vision-service-fallback"
    assert result.detectionMethod == "fallback_camera_unreachable"


def test_analyze_space_usa_deteccion_real_si_la_camara_ip_responde(monkeypatch):
    monkeypatch.setattr(detector, "count_people_in_ip_camera_snapshot", lambda url: 3)

    result = occupancy_calculator.analyze_space(IP_CAMERA_REQUEST)

    assert result.source == "vision-service"
    assert result.detectionMethod == "yolo_ip_camera_snapshot"
    assert result.peopleCount == 3
