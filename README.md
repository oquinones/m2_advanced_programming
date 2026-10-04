# Task Management API

> API REST para la gestión de tareas desarrollada con **FastAPI**. El proyecto aplica los principios de programación orientada a objetos (encapsulamiento, abstracción) y sigue las convenciones de estilo **PEP 8**.

---

## Caracteristicas

- Crear una nueva tarea.
- Obtener una tarea por su `id`.
- Marcar una tarea como completada.
- Listar las tareas caducadas (fecha de vencimiento anterior a hoy y no completadas).
- Persistencia en base de datos **SQLite** mediante **SQLAlchemy**.
- Lógica de negocio encapsulada en una clase de servicio (`TaskManager`).
- Gestión de errores con códigos HTTP apropiados (`200`, `201`, `400`, `404`).
- Script de pruebas independiente con la librería **requests**.

## Stack Tecnologico

| Herramienta | Uso |
|-------------|-----|
| Python 3.14 | Lenguaje principal |
| FastAPI | Framework web |
| Pydantic | Validación y serialización de datos |
| SQLAlchemy | ORM para el acceso a SQLite |
| SQLite | Base de datos (`tasks.db`) |
| Uvicorn | Servidor ASGI para el despliegue en localhost |
| requests | Script de pruebas de los endpoints |

## Estructura del proyecto
```text
m2_advanced_programming/
├── api/
│   ├── __init__.py
│   └── main.py              # Crea la app, implementa la logiva de negocio con TaskManager y manejadores de errores
├── test_main.py             # Script de pruebas con requests
├── requirements.txt         # Dependencias del proyecto (gestionadas con pip)
└── README.md
```

## Modelo de Datos

### Registro de tareas (`TaskResponse`)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `task_id` | `int` | Identificador único (autogenerado) |
| `task_title` | `str` | Título de la tarea |
| `task_content` | `str` | Descripción de la tarea |
| `creation_date` | `datetime` (ISO 8601) | Fecha y hora de creación (autogenerada) |
| `update_date` | `datetime` (ISO 8601) | Fecha y hora de actualizacion (autogenerada) |
| `deadline` | `date` (`YYYY-MM-DD`) | Fecha de vencimiento |
| `task_completed` | `bool` | Indica si la tarea está completada (por defecto `false`) |
| `assigned_user` | `str` | Nombre del usuario que tiene asignada la tarea (por defecto `None`) |


### Creación de tarea (`TaskCreate`)

| Campo | Tipo | Obligatorio | Restricciones |
|-------|------|:-----------:|---------------|
| `task_title` | `str` | Sí | No vacío (tampoco solo espacios); se normalizan los espacios |
| `task_content` | `str` | Sí | No vacío (tampoco solo espacios); se normalizan los espacios |
| `deadline` | `date` | Sí | Formato `YYYY-MM-DD`; `deadline` >= `creation_date` y  `deadline` <= (`creation_date` + 15 dias) |
| `assigned_user` | `str` | No | Nombre del usuario que tiene asignada la tarea (por defecto `None`); se normalizan los espacios |

## Endpoints

| Método | Ruta | Descripción | Éxito | Errores |
|--------|------|-------------|:-----:|:-------:|
| `GET` | `/` | Información de la API | 200 | — |
| `POST` | `/tasks/` | Crear una nueva tarea | 201 | 400 |
| `GET` | `/tasks/{task_id}` | Obtener una tarea por su id | 200 | 400, 404 |
| `PUT` | `/tasks/{task_id}/completar` | Marcar una tarea como completada | 200 | 400, 404 |
| `GET` | `/tasks/caducadas` | Listar las tareas caducadas | 200 | — |

---

## Arquitectura y diseño POO

La aplicación separa responsabilidades en capas:

1. **Modelos Pydantic** (`TaskCreate`, `TaskUpdate`, `TaskResponse`): definen el contrato de entrada y salida de la API y validan los datos recibidos.
2. **Modelo de persistencia** (tabla de tareas en SQLAlchemy): representa la entidad `Task` en la base de datos.
3. **Clase de servicio `TaskManager`**: encapsula toda la lógica de negocio relacionada con las tareas:
   - **transformación del contenido**: `_clean_text` elimina los espacios al inicio y al final y reduce los espacios repetidos a uno (`"  Hola   mundo "` → `"Hola mundo"`),
   - **validaciones**: `task_title` y `task_content` no pueden quedar vacíos tras la limpieza; la fecha del `deadline` no puede ser menor que la fecha de creación `creation_date` y mayor a 15 dias despues de la fecha de creación `creation_date`.
   - **comprobación de fechas**: detección de tareas caducadas,
   - **acceso a la base de datos** mediante una sesión privada (`self.__db`).

   | Método público | Descripción |
   |----------------|-------------|
   | `create_task(data)` | Limpia, valida y guarda una tarea |
   | `get_task(task_id)` | Devuelve la tarea o lanza `TaskNotFoundError` |
   | `mark_completed(task_id)` | Marca la tarea como completada (idempotente) |
   | `get_expired_tasks()` | Tareas no completadas con `deadline` anterior a hoy, ordenadas por fecha |

   Los endpoints no acceden directamente a la base de datos: delegan en `TaskManager`, que oculta los detalles de implementación (**encapsulamiento**) y expone una interfaz sencilla de operaciones (**abstracción**). Los errores de negocio se lanzan como excepciones de dominio (`TaskNotFoundError`, `InvalidTaskError`) que los manejadores de errores de `api/main.py` traducen a `404` y `400`. Los datos de entrada que no superan la validación de Pydantic también devuelven `400` (en lugar del `422` por defecto de FastAPI).
4. **Endpoints FastAPI**: reciben la petición, invocan al servicio y traducen el resultado (o la excepción) al código HTTP correspondiente.

## Instalación

### 1. Crear entorno virtual

```bash
# Windows
python -m venv env
env\Scripts\activate

# Linux/Mac
python -m venv env
source env/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Ejecutar la aplicación

Desde la raíz del proyecto, puedes usar cualquiera de estos comandos:

```bash
# Opción 1: Comando moderno de FastAPI (recomendado)
fastapi dev api/main.py

# Opción 2: Uvicorn tradicional
uvicorn api.main:app --reload
```

La API estará disponible en `http://localhost:8000`

## 4. Uso de los endpoints

### `GET /` — Información de la API

Respuesta `200`:

```json
{"message": "Task Management API"}
```

### `POST /tasks/` — Crear una nueva tarea

Cuerpo (`TaskCreate`):

```json
{
  "task_title": "  Preparar   informe ",
  "task_content": "Resumen mensual",
  "deadline": "2026-10-10",
  "assigned_user": "ana"
}
```

Respuesta `201` (`TaskResponse`), con los textos normalizados:

```json
{
  "task_id": 1,
  "task_title": "Preparar informe",
  "task_content": "Resumen mensual",
  "creation_date": "2026-10-03T19:29:25.204700",
  "update_date": "2026-10-03T19:29:25.204700",
  "deadline": "2026-10-10",
  "task_completed": false,
  "assigned_user": "ana"
}
```

Errores `400`: campos obligatorios ausentes, `task_title`/`task_content` vacíos (o solo espacios), fecha con formato incorrecto, o `deadline` fuera del rango [hoy, hoy + 15 días].

### `GET /tasks/{task_id}` — Obtener una tarea por su id

Respuesta `200` con la tarea (`TaskResponse`).

- `400`: `task_id` no es un entero mayor que 0 (p. ej. `/tasks/abc` o `/tasks/0`).
- `404`: la tarea no existe.

### `PUT /tasks/{task_id}/completar` — Marcar una tarea como completada

No requiere cuerpo. Respuesta `200` con la tarea y `task_completed: true`. Es idempotente: completar una tarea ya completada devuelve `200` sin modificarla.

- `400`: `task_id` no es un entero mayor que 0.
- `404`: la tarea no existe.

### `GET /tasks/caducadas` — Listar las tareas caducadas

Respuesta `200` con una lista de `TaskResponse`: tareas no completadas cuyo `deadline` es anterior a hoy, ordenadas por `deadline` ascendente. Si no hay ninguna, devuelve `[]`.

### Formato de los errores

- Errores de validación de entrada: `{"detail": [ ...lista de errores de Pydantic... ]}`
- Errores de negocio: `{"detail": "mensaje descriptivo"}`, p. ej. `{"detail": "The task with id 990000 does not exist"}`

## 5. Ejecutar tests

Con la aplicación arrancada en `http://localhost:8000`, en otra terminal:

> La base de datos `tasks.db` se crea automáticamente al arrancar la aplicación.

```bash
python test_main.py
```

## Documentación interactiva

Una vez ejecutando la aplicación, puedes acceder a:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
