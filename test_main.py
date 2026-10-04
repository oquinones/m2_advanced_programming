"""Script de pruebas de la Task Management API con la librería requests.

Requiere que la API este en ejcucion en localhost:
    uvicorn api.main:app --reload

Ejecución:
    python test_main.py
"""

from datetime import date, timedelta

import requests

BASE_URL = "http://localhost:8000"
TASKS_URL = f"{BASE_URL}/tasks"
TIMEOUT = 10


def _crear_tarea(dias_hasta_deadline: int = 15, **overrides) -> requests.Response:
    """Send a POST request to /tasks/ with valid, overwritable data."""
    payload = {
        "task_title": "Carga de datos en la BBDD",
        "task_content": "Contenido de prueba",
        "deadline": (date.today() + timedelta(days=dias_hasta_deadline)).isoformat(),
        "assigned_user": "tester",
    }
    payload.update(overrides)
    return requests.post(TASKS_URL, json=payload, timeout=TIMEOUT)


def test_crear_tarea() -> None:
    """Creating a task returns 201 with the data cleaned up and default values set."""
    response = _crear_tarea(task_title="  Job   Control-M  ")
    assert response.status_code == 201, response.text
    data = response.json()
    assert isinstance(data["task_id"], int)
    assert data["task_title"] == "Job Control-M"
    assert data["task_completed"] is False
    assert data["assigned_user"] == "tester"
    assert data["creation_date"] and data["update_date"]


def test_obtener_tarea() -> None:
    """Obtaining an existing task returns 200; a non-existing one returns 404."""
    task_id = _crear_tarea().json()["task_id"]

    response = requests.get(f"{TASKS_URL}/{task_id}", timeout=TIMEOUT)
    assert response.status_code == 200, response.text
    assert response.json()["task_id"] == task_id

    response = requests.get(f"{TASKS_URL}/999999999", timeout=TIMEOUT)
    assert response.status_code == 404, response.text


def test_marcar_completada() -> None:
    """Marking a task as completed returns 200; a non-existing one returns 404."""
    task_id = _crear_tarea().json()["task_id"]
    url = f"{TASKS_URL}/{task_id}/completar"

    for _ in range(2):
        response = requests.put(url, timeout=TIMEOUT)
        assert response.status_code == 200, response.text
        assert response.json()["task_completed"] is True

    response = requests.put(f"{TASKS_URL}/999999999/completar", timeout=TIMEOUT)
    assert response.status_code == 404, response.text


def test_obtener_tarea_inexistente() -> None:
    """Obtaining a non-existing task returns 404."""
    response = requests.get(f"{TASKS_URL}/999999999", timeout=TIMEOUT)
    assert response.status_code == 404, response.text
    assert "task not found" in response.json()["detail"]


def test_obtener_tareas_caducadas() -> None:
    """Obtaining expired tasks returns 200; they are not completed, expire before today,
    and are ordered.
    """
    task_id = _crear_tarea().json()["task_id"]

    response = requests.get(f"{TASKS_URL}/caducadas", timeout=TIMEOUT)
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
    """Invalid input data returns 400."""
    casos = {
        "falta el título": {
            "contenido": "Sin título",
            "deadline": date.today().isoformat(),
        },
        "título vacío": {
            "titulo": "",
            "contenido": "Titulo vacío",
            "deadline": date.today().isoformat(),
        },
        "título solo con espacios": {
            "titulo": "   ",
            "contenido": "Título solo con espacios",
            "deadline": date.today().isoformat(),
        },
        "fecha con formato incorrecto": {
            "titulo": "Tarea con fecha mal formateada",
            "contenido": "x",
            "deadline": "31/12/2026",
        },
        "año fuera de rango": {
            "titulo": "Tarea con año fuera de rango",
            "contenido": "x",
            "deadline": "1990-01-01",
        },
    }
    for detail, payload in casos.items():
        response = requests.post(f"{TASKS_URL}/", json=payload, timeout=TIMEOUT)
        assert response.status_code == 400, f"{detail}: {payload} {response.text}"
        assert "detail" in response.json(), detail

    for dias in (-1, 16):
        response = _crear_tarea(dias_hasta_deadline=dias)
        assert response.status_code == 400, f"deadline at {dias} days: {response.text}"

    response = requests.post(
        TASKS_URL, json={"task_title": "Sin campos"}, timeout=TIMEOUT
    )
    assert response.status_code == 400, f"campos obligatorios: {response.text}"

    for url in (f"{TASKS_URL}/abc", f"{TASKS_URL}/0"):
        response = requests.get(url, timeout=TIMEOUT)
        assert response.status_code == 400, f"{url}: {response.text}"

    response = requests.put(f"{TASKS_URL}/abc/completar", timeout=TIMEOUT)
    assert response.status_code == 400, f"PUT id no numérico: {response.text}"


if __name__ == "__main__":
    print("Ejecutando tests...")
    tests = [
        test_crear_tarea,
        test_obtener_tarea,
        test_marcar_completada,
        test_obtener_tareas_caducadas,
        test_datos_incorrectos,
        test_obtener_tarea_inexistente,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  OK    {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FALLO {test.__name__}: {exc}")
        except requests.ConnectionError:
            print(f"No se puede conectar con {BASE_URL}. ¿Está el servidor arrancado?")
            raise SystemExit(1) from None
    print(f"Tests completados: {len(tests) - failed}/{len(tests)} correctos")
    raise SystemExit(1 if failed else 0)
