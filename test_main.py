"""Script de pruebas de la Task Management API con la librería requests.

Requiere que la API este en ejcucion en localhost:
    uvicorn api.main:app --reload

Ejecución:
    python test_main.py
"""

from datetime import date, timedelta

import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 10


def _crear_tarea(dias_hasta_deadline: int = 15, **overrides) -> requests.Response:
    """Envía un POST a /tasks/ con datos válidos, sobrescribibles."""
    payload = {
        "task_title": "Carga de datos en la BBDD",
        "task_content": "Contenido de prueba",
        "deadline": (date.today() + timedelta(days=dias_hasta_deadline)).isoformat(),
        "assigned_user": "tester",
    }
    payload.update(overrides)
    return requests.post(f"{BASE_URL}/tasks/", json=payload, timeout=TIMEOUT)


def test_crear_tarea() -> None:
    """Crear una tarea devuelve 201 con los datos limpios y valores por defecto."""
    response = _crear_tarea(task_title="  Hola   mundo  ")
    assert response.status_code == 201, response.text
    data = response.json()
    assert isinstance(data["task_id"], int)
    assert data["task_title"] == "Hola mundo"
    assert data["task_completed"] is False
    assert data["assigned_user"] == "tester"
    assert data["creation_date"] and data["update_date"]


def test_obtener_tarea() -> None:
    """Obtener una tarea existente devuelve 200; una inexistente 404."""
    task_id = _crear_tarea().json()["task_id"]

    response = requests.get(f"{BASE_URL}/tasks/{task_id}", timeout=TIMEOUT)
    assert response.status_code == 200, response.text
    assert response.json()["task_id"] == task_id

    response = requests.get(f"{BASE_URL}/tasks/999999999", timeout=TIMEOUT)
    assert response.status_code == 404, response.text


def test_marcar_completada() -> None:
    """Completar una tarea devuelve 200; inexistente 404."""
    task_id = _crear_tarea().json()["task_id"]
    url = f"{BASE_URL}/tasks/{task_id}/completar"

    for _ in range(2):
        response = requests.put(url, timeout=TIMEOUT)
        assert response.status_code == 200, response.text
        assert response.json()["task_completed"] is True

    response = requests.put(f"{BASE_URL}/tasks/999999999/completar", timeout=TIMEOUT)
    assert response.status_code == 404, response.text


def test_obtener_tareas_caducadas() -> None:
    """Las caducadas no están completadas, vencen antes de hoy y van ordenadas."""
    task_id = _crear_tarea().json()["task_id"]

    response = requests.get(f"{BASE_URL}/tasks/caducadas", timeout=TIMEOUT)
    assert response.status_code == 200, response.text
    tareas = response.json()
    assert isinstance(tareas, list)

    today = date.today()
    deadlines = [date.fromisoformat(t["deadline"]) for t in tareas]
    assert all(d < today for d in deadlines)
    assert all(t["task_completed"] is False for t in tareas)
    assert deadlines == sorted(deadlines)
    assert task_id not in {t["task_id"] for t in tareas}


def test_datos_incorrectos() -> None:
    """Datos de entrada no válidos devuelven 400."""
    casos = {
        "título solo espacios": {"task_title": "   "},
        "contenido vacío": {"task_content": ""},
        "contenido solo espacios": {"task_content": "   "},
        "formato de fecha": {"deadline": "03-10-2026"},
    }
    for nombre, overrides in casos.items():
        response = _crear_tarea(**overrides)
        assert response.status_code == 400, f"{nombre}: {response.text}"

    for dias in (-1, 16):
        response = _crear_tarea(dias_hasta_deadline=dias)
        assert response.status_code == 400, f"deadline a {dias} días: {response.text}"

    response = requests.post(
        f"{BASE_URL}/tasks/", json={"task_title": "Sin campos"}, timeout=TIMEOUT
    )
    assert response.status_code == 400, f"campos obligatorios: {response.text}"

    for url in (f"{BASE_URL}/tasks/abc", f"{BASE_URL}/tasks/0"):
        response = requests.get(url, timeout=TIMEOUT)
        assert response.status_code == 400, f"{url}: {response.text}"

    response = requests.put(f"{BASE_URL}/tasks/abc/completar", timeout=TIMEOUT)
    assert response.status_code == 400, f"PUT id no numérico: {response.text}"


if __name__ == "__main__":
    print("Ejecutando tests...")
    tests = [
        test_crear_tarea,
        test_obtener_tarea,
        test_marcar_completada,
        test_obtener_tareas_caducadas,
        test_datos_incorrectos,
    ]
    fallos = 0
    for test in tests:
        try:
            test()
            print(f"  OK    {test.__name__}")
        except AssertionError as exc:
            fallos += 1
            print(f"  FALLO {test.__name__}: {exc}")
        except requests.ConnectionError:
            print(f"No se puede conectar con {BASE_URL}. ¿Está el servidor arrancado?")
            raise SystemExit(1) from None
    print(f"Tests completados: {len(tests) - fallos}/{len(tests)} correctos")
    raise SystemExit(1 if fallos else 0)
