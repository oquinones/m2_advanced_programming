"""
Script principal de la API de Gestión de Tareas

Este script implementa una API RESTful para la gestión de tareas utilizando FastAPI.
Proporciona endpoints para crear, obtener, actualizar y listar tareas,
así como para manejar errores específicos de la aplicación.
"""

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
APP_DESCRIPTION = "API for Task Management"
# LOCAL_TIMEZONE = ZoneInfo("Europe/Madrid")

# Mark: --- FastAPI setup ---
app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION, version=APP_VERSION)

# Mark: --- DB setup ---
DATABASE_URL = "sqlite:///./tasks.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


class TaskDB(Base):
    """Database schema for the tasks table in the BBDD."""

    __tablename__ = "tasks"

    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_title: Mapped[str] = mapped_column(String(150), nullable=False)
    task_content: Mapped[str] = mapped_column(String(300), nullable=False)
    creation_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    update_date: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
    deadline: Mapped[date] = mapped_column(Date, nullable=False)
    task_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_user: Mapped[str | None] = mapped_column(String(100), nullable=True)


Base.metadata.create_all(bind=engine)


# Mark: --- Pydantic model ---
class TaskCreate(BaseModel):
    """Input data model for creating a task."""

    task_title: str = Field(..., min_length=1, description="Task title")
    task_content: str = Field(..., min_length=1, description="Task content")
    deadline: date = Field(..., description="Due date")
    assigned_user: str | None = Field(
        default=None, min_length=4, description="User assigned to the task"
    )


class TaskUpdate(BaseModel):
    """Input data model for updating a task."""

    task_completed: bool = Field(description="Task completion status")
    update_date: datetime = Field(
        default_factory=datetime.now, description="Update date"
    )


class TaskResponse(BaseModel):
    """Output data model for task responses."""

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
    """The requested task does not exist."""

    def __init__(self, task_id: int) -> None:
        super().__init__(f"The task with id {task_id} does not exist")
        self.task_id = task_id


class InvalidTaskError(Exception):
    """The task data does not comply with the business rules."""


# Mark: --- Task Manager Service ---
class TaskManager:
    """Encapsulates the business logic and data access for tasks."""

    MAX_DEADLINE_DAYS = 15

    def __init__(self, db: Session) -> None:
        self.__db = db

    # Mark: --- Local methods ---
    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove leading and trailing spaces and reduce repetitions to one."""
        return " ".join(text.split())

    def _validate_deadline(self, deadline: date, creation_date: date) -> None:
        """Check that the deadline is a date between the creation date and +15 days."""

        if not isinstance(deadline, date) or isinstance(deadline, datetime):
            raise InvalidTaskError("The deadline must be a date (YYYY-MM-DD)")

        if deadline < creation_date:
            raise InvalidTaskError(
                "The deadline cannot be earlier than the creation date"
            )
        max_deadline = creation_date + timedelta(days=self.MAX_DEADLINE_DAYS)

        if deadline > max_deadline:
            raise InvalidTaskError(
                f"The deadline cannot exceed {self.MAX_DEADLINE_DAYS} days "
                "from the creation date"
            )

    # Mark: --- Public methods ---
    def create_task(self, data: TaskCreate) -> TaskDB:
        """Cleans, validates and saves a task."""
        title = self._clean_text(data.task_title)
        content = self._clean_text(data.task_content)
        if not title:
            raise InvalidTaskError("The task title cannot be empty")
        if not content:
            raise InvalidTaskError("The task content cannot be empty")

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
        """Returns the task or throws a TaskNotFoundError."""
        task = self.__db.get(TaskDB, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def mark_completed(self, task_id: int) -> TaskDB:
        """Marks the task as completed."""
        task = self.get_task(task_id)
        if not task.task_completed:
            now = datetime.now()
            task.task_completed = True
            task.update_date = now
            self.__db.commit()
            self.__db.refresh(task)
        return task

    def get_expired_tasks(self) -> list[TaskDB]:
        """Returns expired tasks."""
        stmt = (
            select(TaskDB)
            .where(TaskDB.task_completed.is_(False), TaskDB.deadline < date.today())
            .order_by(TaskDB.deadline)
        )
        return list(self.__db.scalars(stmt))


# Mark: --- Dependencies ---
def get_db() -> Iterator[Session]:
    """Opens a database session per request and closes it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_task_manager(db: Annotated[Session, Depends(get_db)]) -> TaskManager:
    """Provides the task service to the endpoints."""
    return TaskManager(db)


TaskManagerDep = Annotated[TaskManager, Depends(get_task_manager)]
TaskIdPath = Annotated[int, Path(gt=0, description="Id of the task")]


# Mark: --- Error handlers ---
@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Returns 400 instead of 422 when the input data is invalid."""
    del request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(InvalidTaskError)
async def invalid_task_handler(request: Request, exc: InvalidTaskError) -> JSONResponse:
    """Returns 400 when the task data is invalid."""
    del request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)}
    )


@app.exception_handler(TaskNotFoundError)
async def task_not_found_handler(
    request: Request, exc: TaskNotFoundError
) -> JSONResponse:
    """Returns 404 when the task is not found."""
    del request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)}
    )


# Mark: --- Endpoints implementation ---
@app.post("/tasks/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def post_create_task(task: TaskCreate, manager: TaskManagerDep) -> TaskDB:
    """Creates a new task."""
    return manager.create_task(task)


# /tasks/caducadas tiene que declararse antes que /tasks/{task_id};
# si no, FastAPI intentaría interpretar "caducadas" como un id
@app.get("/tasks/caducadas", response_model=list[TaskResponse])
def get_expired_tasks(manager: TaskManagerDep) -> list[TaskDB]:
    """Returns expired tasks."""
    return manager.get_expired_tasks()


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: TaskIdPath, manager: TaskManagerDep) -> TaskDB:
    """Returns a task by its id."""
    return manager.get_task(task_id)


@app.put("/tasks/{task_id}/completar", response_model=TaskResponse)
def mark_completed(task_id: TaskIdPath, manager: TaskManagerDep) -> TaskDB:
    """Marks a task as completed."""
    return manager.mark_completed(task_id)


@app.get("/")
def root() -> dict[str, str]:
    """Root endpoint of the API."""
    return {"message": "Task Management API"}
