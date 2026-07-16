from app import storage


def test_get_analysis_inexistente_devuelve_none():
    assert storage.get_analysis("no-existe") is None


def test_save_and_get_analysis_guarda_el_ultimo_valor():
    storage.save_analysis("biblioteca-cisco", {"peopleCount": 3})
    storage.save_analysis("biblioteca-cisco", {"peopleCount": 7})

    assert storage.get_analysis("biblioteca-cisco") == {"peopleCount": 7}


def test_get_all_analysis_incluye_todos_los_espacios_guardados():
    storage.save_analysis("espacio-a", {"peopleCount": 1})
    storage.save_analysis("espacio-b", {"peopleCount": 2})

    all_analysis = storage.get_all_analysis()

    assert {"peopleCount": 1} in all_analysis
    assert {"peopleCount": 2} in all_analysis


def test_get_frame_inexistente_devuelve_none():
    assert storage.get_frame("no-existe") is None


def test_save_and_get_frame_guarda_el_ultimo_valor():
    storage.save_frame("biblioteca-cisco", b"jpeg-viejo")
    storage.save_frame("biblioteca-cisco", b"jpeg-nuevo")

    assert storage.get_frame("biblioteca-cisco") == b"jpeg-nuevo"
