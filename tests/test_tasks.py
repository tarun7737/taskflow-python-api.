from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import database
from app.database import Base, get_db
from app.main import app
from app.models import Task, TaskPriority, TaskStatus


@pytest.fixture
def test_engine() -> Iterator[Engine]:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Iterator[Session]:
    Base.metadata.create_all(bind=test_engine)
    test_session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )
    with test_session_factory() as session:
        yield session


@pytest.fixture
def client(
    test_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    monkeypatch.setattr(database, "engine", test_engine)
    test_session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )

    def override_get_db() -> Iterator[Session]:
        with test_session_factory() as session:
            yield session

    monkeypatch.setitem(app.dependency_overrides, get_db, override_get_db)
    with TestClient(app) as test_client:
        yield test_client


def test_read_root(client: TestClient):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to TaskFlow API"}


def test_create_task(client: TestClient):
    response = client.post(
        "/tasks",
        json={
            "title": "Prepare portfolio",
            "description": "Finish the TaskFlow API",
            "status": "in_progress",
            "priority": "high",
            "due_date": "2026-11-01",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["title"] == "Prepare portfolio"
    assert body["description"] == "Finish the TaskFlow API"
    assert body["status"] == "in_progress"
    assert body["priority"] == "high"
    assert body["due_date"] == "2026-11-01"
    assert body["created_at"] is not None
    assert body["updated_at"] is not None


def test_create_task_uses_defaults(client: TestClient):
    response = client.post("/tasks", json={"title": "Default task"})

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert response.json()["priority"] == "medium"
    assert response.json()["due_date"] is None


@pytest.mark.parametrize(
    "invalid_data",
    [
        {"title": "Bad status", "status": "started"},
        {"title": "Bad priority", "priority": "urgent"},
        {"title": "Bad date", "due_date": "not-a-date"},
        {"title": "   "},
        {"description": "Title is required"},
    ],
)
def test_create_task_rejects_invalid_input(
    client: TestClient,
    invalid_data: dict[str, str],
):
    response = client.post("/tasks", json=invalid_data)

    assert response.status_code == 422


def test_list_tasks(client: TestClient):
    client.post("/tasks", json={"title": "First task"})
    client.post("/tasks", json={"title": "Second task"})

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["title"] for task in response.json()] == [
        "First task",
        "Second task",
    ]


def test_list_tasks_when_empty(client: TestClient):
    response = client.get("/tasks")

    assert response.status_code == 200
    assert response.json() == []


def test_list_tasks_filters_by_status(client: TestClient):
    client.post("/tasks", json={"title": "Waiting", "status": "pending"})
    client.post("/tasks", json={"title": "Finished", "status": "completed"})

    response = client.get("/tasks", params={"status": "pending"})

    assert response.status_code == 200
    assert [task["title"] for task in response.json()] == ["Waiting"]


def test_list_tasks_filters_by_priority(client: TestClient):
    client.post("/tasks", json={"title": "Urgent", "priority": "high"})
    client.post("/tasks", json={"title": "Normal", "priority": "medium"})

    response = client.get("/tasks", params={"priority": "high"})

    assert response.status_code == 200
    assert [task["title"] for task in response.json()] == ["Urgent"]


def test_list_tasks_combines_status_and_priority_filters(client: TestClient):
    client.post(
        "/tasks",
        json={"title": "Match", "status": "pending", "priority": "high"},
    )
    client.post(
        "/tasks",
        json={"title": "Wrong status", "status": "completed", "priority": "high"},
    )
    client.post(
        "/tasks",
        json={"title": "Wrong priority", "status": "pending", "priority": "low"},
    )

    response = client.get(
        "/tasks",
        params={"status": "pending", "priority": "high"},
    )

    assert response.status_code == 200
    assert [task["title"] for task in response.json()] == ["Match"]


@pytest.mark.parametrize(
    "filters",
    [
        {"status": "started"},
        {"priority": "urgent"},
    ],
)
def test_list_tasks_rejects_invalid_filters(
    client: TestClient,
    filters: dict[str, str],
):
    response = client.get("/tasks", params=filters)

    assert response.status_code == 422


def test_get_task(client: TestClient):
    created = client.post("/tasks", json={"title": "Find me"})

    response = client.get(f"/tasks/{created.json()['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Find me"


def test_get_missing_task_returns_404(client: TestClient):
    response = client.get("/tasks/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_update_task(client: TestClient):
    created = client.post(
        "/tasks",
        json={
            "title": "Original task",
            "description": "Old description",
        },
    )
    task_id = created.json()["id"]

    response = client.put(
        f"/tasks/{task_id}",
        json={
            "title": "Updated task",
            "description": "New description",
            "status": "completed",
            "priority": "low",
            "due_date": "2026-12-31",
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated task"
    assert response.json()["description"] == "New description"
    assert response.json()["status"] == "completed"
    assert response.json()["priority"] == "low"
    assert response.json()["due_date"] == "2026-12-31"


def test_update_task_rejects_invalid_input(client: TestClient):
    created = client.post("/tasks", json={"title": "Update me"})

    response = client.put(
        f"/tasks/{created.json()['id']}",
        json={
            "title": "Updated task",
            "status": "blocked",
            "priority": "medium",
        },
    )

    assert response.status_code == 422


def test_update_task_rejects_invalid_date(client: TestClient):
    created = client.post("/tasks", json={"title": "Update date"})

    response = client.put(
        f"/tasks/{created.json()['id']}",
        json={"title": "Updated task", "due_date": "not-a-date"},
    )

    assert response.status_code == 422


def test_update_missing_task_returns_404(client: TestClient):
    response = client.put(
        "/tasks/999",
        json={"title": "Missing task"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_delete_task(client: TestClient):
    created = client.post("/tasks", json={"title": "Delete me"})
    task_id = created.json()["id"]

    response = client.delete(f"/tasks/{task_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/tasks/{task_id}").status_code == 404


def test_delete_missing_task_returns_404(client: TestClient):
    response = client.delete("/tasks/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/tasks/not-an-id", None),
        ("put", "/tasks/not-an-id", {"title": "No task"}),
        ("delete", "/tasks/not-an-id", None),
    ],
)
def test_task_endpoints_reject_non_integer_ids(
    client: TestClient,
    method: str,
    path: str,
    body: dict[str, str] | None,
):
    response = client.request(method, path, json=body)

    assert response.status_code == 422


def test_task_can_be_stored_and_retrieved(db_session: Session):
    task = Task(
        title="Prepare portfolio",
        description="Finish the TaskFlow API",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        due_date=date(2026, 11, 1),
    )
    db_session.add(task)
    db_session.commit()
    task_id = task.id
    db_session.expunge(task)

    retrieved_task = db_session.scalar(
        select(Task).where(Task.title == "Prepare portfolio")
    )

    assert retrieved_task is not None
    assert retrieved_task.id == task_id
    assert retrieved_task.description == "Finish the TaskFlow API"
    assert retrieved_task.status is TaskStatus.IN_PROGRESS
    assert retrieved_task.priority is TaskPriority.HIGH
    assert retrieved_task.due_date == date(2026, 11, 1)
    assert retrieved_task.created_at is not None
    assert retrieved_task.updated_at is not None


def test_startup_creates_database_tables(
    monkeypatch: pytest.MonkeyPatch,
    test_engine: Engine,
):
    monkeypatch.setattr(database, "engine", test_engine)

    with TestClient(app):
        assert inspect(test_engine).has_table("tasks")
