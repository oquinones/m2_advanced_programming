"""
Test script for the task management API using the requests library.

Requires the API to be running on localhost:
    uvicorn api.main:app --reload

Run (from the project's root directory, which is the same as the server's):
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
        "task_content": "Tarea de prueba de carga de datos",
        "deadline": (date.today() + timedelta(days=dias_hasta_deadline)).isoformat(),
        "assigned_user": "tester",
    }
    payload.update(overrides)
    return requests.post(TASKS_URL, json=payload, timeout=TIMEOUT)


def test_create_task() -> None:
    """Creating a task returns 201 with the data cleaned up and default values set."""
    response = _crear_tarea(
        task_title="  Job   Control-M  ",
        task_content="  Tarea de prueba   Control-M  ",
        assigned_user="tester",
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert isinstance(data["task_id"], int)
    assert data["task_title"] == "Job Control-M"
    assert data["task_completed"] is False
    assert data["assigned_user"] == "tester"
    assert data["creation_date"] and data["update_date"]


def test_get_task() -> None:
    """Obtaining an existing task returns 200; a non-existing one returns 404."""
    task_id = _crear_tarea().json()["task_id"]

    response = requests.get(f"{TASKS_URL}/{task_id}", timeout=TIMEOUT)
    assert response.status_code == 200, response.text
    assert response.json()["task_id"] == task_id

    response = requests.get(f"{TASKS_URL}/990000", timeout=TIMEOUT)
    assert response.status_code == 404, response.text


def test_mark_as_completed() -> None:
    """Marking a task as completed returns 200; a non-existing one returns 404."""
    task_id = _crear_tarea().json()["task_id"]
    url = f"{TASKS_URL}/{task_id}/completar"

    for _ in range(2):
        response = requests.put(url, timeout=TIMEOUT)
        assert response.status_code == 200, response.text
        assert response.json()["task_completed"] is True

    response = requests.put(f"{TASKS_URL}/990000/completar", timeout=TIMEOUT)
    assert response.status_code == 404, response.text


def test_delete_task() -> None:
    """Deleting a task returns 204 and the task no longer exists; again returns 404."""
    task_id = _crear_tarea().json()["task_id"]
    url = f"{TASKS_URL}/{task_id}"

    response = requests.delete(url, timeout=TIMEOUT)
    assert response.status_code == 204, response.text
    assert response.content == b""

    response = requests.get(url, timeout=TIMEOUT)
    assert response.status_code == 404, response.text

    response = requests.delete(url, timeout=TIMEOUT)
    assert response.status_code == 404, response.text


def test_get_nonexistent_task() -> None:
    """Obtaining a non-existing task returns 404."""
    response = requests.get(f"{TASKS_URL}/990000", timeout=TIMEOUT)
    assert response.status_code == 404, response.text
    assert "does not exist" in response.json()["detail"]


def test_invalid_data() -> None:
    """Invalid input data returns 400."""
    casos = {
        "missing title": {
            "task_content": "Untitled task",
            "deadline": date.today().isoformat(),
            "assigned_user": "tester",
        },
        "empty title": {
            "task_title": "",
            "task_content": "Empty Title",
            "deadline": date.today().isoformat(),
            "assigned_user": "tester",
        },
        "title with only spaces": {
            "task_title": "   ",
            "task_content": "Title with only spaces",
            "deadline": date.today().isoformat(),
            "assigned_user": "tester",
        },
        "date in incorrect format": {
            "task_title": "Task with incorrect date format",
            "task_content": "x",
            "deadline": "31/12/2026",
            "assigned_user": "tester",
        },
        "year out of range": {
            "task_title": "Task with year out of range",
            "task_content": "x",
            "deadline": "1990-01-01",
            "assigned_user": "tester",
        },
        "missing content": {
            "task_title": "Task without content",
            "deadline": date.today().isoformat(),
            "assigned_user": "tester",
        },
        "empty content": {
            "task_title": "Task with empty content",
            "task_content": "",
            "deadline": date.today().isoformat(),
            "assigned_user": "tester",
        },
        "assigned_user with only spaces": {
            "task_title": "Task with assigned_user only with spaces",
            "task_content": "x",
            "deadline": date.today().isoformat(),
            "assigned_user": "   ",
        },
    }
    for name, payload in casos.items():
        print(f"Testing case: {name}, payload={payload}")
        response = requests.post(TASKS_URL, json=payload, timeout=TIMEOUT)
        assert response.status_code == 400, f"{name}: {payload} {response.text}"
        assert "detail" in response.json(), name

    for dias in (-1, 16):
        print(f"Testing case: deadline at {dias} days")
        response = _crear_tarea(dias_hasta_deadline=dias)
        assert response.status_code == 400, f"deadline at {dias} days: {response.text}"

    response = requests.post(
        TASKS_URL, json={"task_title": "Sin campos"}, timeout=TIMEOUT
    )
    assert response.status_code == 400, f"required fields: {response.text}"

    for url in (f"{TASKS_URL}/abc", f"{TASKS_URL}/0"):
        response = requests.get(url, timeout=TIMEOUT)
        assert response.status_code == 400, f"{url}: {response.text}"

    response = requests.put(f"{TASKS_URL}/abc/completar", timeout=TIMEOUT)
    assert response.status_code == 400, f"PUT non-numeric ID: {response.text}"

    for url in (f"{TASKS_URL}/abc", f"{TASKS_URL}/0"):
        response = requests.delete(url, timeout=TIMEOUT)
        assert response.status_code == 400, f"DELETE {url}: {response.text}"


if __name__ == "__main__":
    print("\033[1;34mRunning tests...\033[0m")
    tests = [
        test_create_task,
        test_get_task,
        test_mark_as_completed,
        test_delete_task,
        test_get_nonexistent_task,
        test_invalid_data,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"\033[32m  OK\033[0m    {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"\033[31m  FALLO\033[0m {test.__name__}: {exc}")
        except requests.ConnectionError:
            print(f"No se puede conectar con {BASE_URL}. ¿Está el servidor arrancado?")
            raise SystemExit(1) from None
    print(
        f"\033[1;34mTests completed: {len(tests) - failed}/{len(tests)} "
        "correctos\033[0m"
    )
    raise SystemExit(1 if failed else 0)
