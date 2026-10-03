"""Main module of the Task Management API"""

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, Path, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    String,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

APP_TITLE = "Task Management API"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "API para la gestión de tareas."

app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION, version=APP_VERSION)

# Mark: --- DB setup ---
DATABASE_URL = "sqlite:///./tasks.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


class TaskDB(Base):
    """Modelo de la tabla de tareas en la base de datos."""

    __tablename__ = "tasks"

    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_title: Mapped[str] = mapped_column(String(150), nullable=False)
    task_content: Mapped[str] = mapped_column(String(300), nullable=False)
    creation_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    update_date: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    deadline: Mapped[date] = mapped_column(Date, nullable=False)
    task_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_user: Mapped[str | None] = mapped_column(String(100), nullable=True)


Base.metadata.create_all(bind=engine)


# Mark: --- Pydantic model ---
class TaskCreate(BaseModel):
    """Datos de entrada para crear una tarea."""

    task_title: str = Field(..., min_length=1, description="Título de la tarea")
    task_content: str = Field(..., min_length=1, description="Contenido de la tarea")
    deadline: date = Field(..., description="Fecha de vencimiento")
    assigned_user: str | None = Field(
        default=None, min_length=1, description="Usuario asignado a la tarea"
    )


class TaskUpdate(BaseModel):
    """Datos de entrada para actualizar una tarea."""

    task_completed: bool = Field(description="Estado de completado")


class TaskResponse(BaseModel):
    """Datos de salida de la API para una tarea."""

    model_config = ConfigDict(from_attributes=True)

    task_id: int
    task_title: str
    task_content: str
    creation_date: datetime
    update_date: datetime
    deadline: date
    task_completed: bool
    assigned_user: str | None = None


# Mark: --- Domain exceptions ---
class TaskNotFoundError(Exception):
    """La tarea solicitada no existe."""

    def __init__(self, task_id: int) -> None:
        super().__init__(f"No existe la tarea con id {task_id}")
        self.task_id = task_id


class InvalidTaskError(Exception):
    """Los datos de la tarea no cumplen las reglas de negocio."""


# Mark: --- Task Manager Service ---
class TaskManager:
    """Encapsula la lógica de negocio y el acceso a datos de las tareas."""

    MAX_DEADLINE_DAYS = 15

    def __init__(self, db: Session) -> None:
        self.__db = db

    # Mark: --- Private methods ---
    @staticmethod
    def _clean_text(text: str) -> str:
        """Elimina espacios al inicio/final y reduce los repetidos a uno."""
        return " ".join(text.split())

    def _validate_deadline(self, deadline: date, creation_date: date) -> None:
        """Comprueba que el deadline esté entre la creación y +15 días."""
        if deadline < creation_date:
            raise InvalidTaskError(
                "deadline no puede ser anterior a la fecha de creación"
            )
        max_deadline = creation_date + timedelta(days=self.MAX_DEADLINE_DAYS)
        if deadline > max_deadline:
            raise InvalidTaskError(
                f"La fecha dedeadline no puede superar {self.MAX_DEADLINE_DAYS} días "
                "desde la fecha de creación"
            )

    # Mark: --- Public methods ---
    def create_task(self, data: TaskCreate) -> TaskDB:
        """Limpia, valida y guarda una tarea."""
        title = self._clean_text(data.task_title)
        content = self._clean_text(data.task_content)
        if not title:
            raise InvalidTaskError("El título de la tarea no puede estar vacío")
        if not content:
            raise InvalidTaskError("El contenido de la tarea no puede estar vacío")

        assigned_user = None
        if data.assigned_user is not None:
            assigned_user = self._clean_text(data.assigned_user) or None

        now = datetime.now()
        self._validate_deadline(data.deadline, now.date())

        task = TaskDB(
            task_title=title,
            task_content=content,
            creation_date=now,
            update_date=now,
            deadline=data.deadline,
            task_completed=False,
            assigned_user=assigned_user,
        )
        self.__db.add(task)
        self.__db.commit()
        self.__db.refresh(task)
        return task

    def get_task(self, task_id: int) -> TaskDB:
        """Devuelve la tarea o lanza TaskNotFoundError."""
        task = self.__db.get(TaskDB, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def mark_completed(self, task_id: int) -> TaskDB:
        """Marca la tarea como completada (idempotente)."""
        task = self.get_task(task_id)
        if not task.task_completed:
            task.task_completed = True
            self.__db.commit()
            self.__db.refresh(task)
        return task

    def get_expired_tasks(self) -> list[TaskDB]:
        """Tareas no completadas con deadline anterior a hoy, ordenadas por fecha."""
        stmt = (
            select(TaskDB)
            .where(TaskDB.task_completed.is_(False), TaskDB.deadline < date.today())
            .order_by(TaskDB.deadline)
        )
        return list(self.__db.scalars(stmt))


# Mark: --- Dependencies ---
def get_db() -> Iterator[Session]:
    """Abre una sesión de base de datos por petición y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_task_manager(db: Annotated[Session, Depends(get_db)]) -> TaskManager:
    """Proporciona el servicio de tareas a los endpoints."""
    return TaskManager(db)


TaskManagerDep = Annotated[TaskManager, Depends(get_task_manager)]
TaskIdPath = Annotated[int, Path(gt=0, description="Id de la tarea")]


# Mark: --- Error handlers ---
@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Devuelve 400 en lugar de 422 cuando los datos de entrada no son válidos."""
    del request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(InvalidTaskError)
async def invalid_task_handler(request: Request, exc: InvalidTaskError) -> JSONResponse:
    """Traduce InvalidTaskError a 400."""
    del request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)}
    )


@app.exception_handler(TaskNotFoundError)
async def task_not_found_handler(
    request: Request, exc: TaskNotFoundError
) -> JSONResponse:
    """Traduce TaskNotFoundError a 404."""
    del request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)}
    )


# Mark: --- Endpoints implementation ---
@app.post("/tasks/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def crear_tarea(task: TaskCreate, manager: TaskManagerDep) -> TaskDB:
    """Crea una nueva tarea."""
    return manager.create_task(task)


# /tasks/caducadas tiene que declararse antes que /tasks/{task_id};
# si no, FastAPI intentaría interpretar "caducadas" como un id
@app.get("/tasks/caducadas", response_model=list[TaskResponse])
def obtener_tareas_caducadas(manager: TaskManagerDep) -> list[TaskDB]:
    """Lista las tareas caducadas."""
    return manager.get_expired_tasks()


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def obtener_tarea(task_id: TaskIdPath, manager: TaskManagerDep) -> TaskDB:
    """Obtiene una tarea por su id."""
    return manager.get_task(task_id)


@app.put("/tasks/{task_id}/completar", response_model=TaskResponse)
def marcar_completada(task_id: TaskIdPath, manager: TaskManagerDep) -> TaskDB:
    """Marca una tarea como completada."""
    return manager.mark_completed(task_id)


@app.get("/")
def root() -> dict[str, str]:
    """Endpoint raíz de la API."""
    return {"message": "Task Management API"}
