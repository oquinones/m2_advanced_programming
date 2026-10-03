from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import List

app = FastAPI(title="Task Management API", version="1.0.0")

# Modelos Pydantic
class TaskCreate(BaseModel):
    titulo: str = Field(min_length=1, description="Título de la tarea")
    contenido: str = Field(min_length=1, description="Contenido de la tarea")
    deadline: date = Field(description="Fecha de vencimiento")

class TaskUpdate(BaseModel):
    completada: bool = Field(description="Estado de completado")

class TaskResponse(BaseModel):
    id: int
    titulo: str
    contenido: str
    deadline: date
    completada: bool
    fecha_creacion: datetime

# Persistencia en SQLite
DATABASE_URL = "sqlite:///./tasks.db"

# TODO: Configurar la conexión a la base de datos y definir el modelo de la tabla de tareas
# (por ejemplo, con SQLAlchemy)

# TODO: Implementar clase TaskManager con lógica de negocio
# class TaskManager:
#     ...

# TODO: Devolver 400 cuando los datos de entrada no sean válidos
# (por defecto FastAPI responde 422)

# TODO: Implementar endpoints
# @app.post("/tasks/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
# def crear_tarea(task: TaskCreate):
#     ...

# /tasks/caducadas tiene que declararse antes que /tasks/{task_id};
# si no, FastAPI intentaría interpretar "caducadas" como un id
# @app.get("/tasks/caducadas", response_model=List[TaskResponse])
# def obtener_tareas_caducadas():
#     ...

# @app.get("/tasks/{task_id}", response_model=TaskResponse)
# def obtener_tarea(task_id: int):
#     ...

# @app.put("/tasks/{task_id}/completar", response_model=TaskResponse)
# def marcar_completada(task_id: int):
#     ...

@app.get("/")
def root():
    return {"message": "Task Management API"}
