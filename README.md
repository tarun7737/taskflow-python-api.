# TaskFlow — Task Management REST API

TaskFlow is a small REST API for managing tasks. It is a beginner-friendly Python portfolio project built with FastAPI, SQLAlchemy, SQLite, Pydantic, and Pytest.

## Implemented features

- Create, list, retrieve, update, and delete tasks.
- Filter task lists by status, priority, or both.
- Validate required titles, dates, and supported status and priority values.
- Persist tasks in a local SQLite database.
- Return clear `404 Not Found` errors when a requested task does not exist.
- Generate interactive API documentation through FastAPI.

## Technology stack

- Python 3.10 or newer (the current development environment uses Python 3.14.2)
- FastAPI and Uvicorn
- SQLAlchemy ORM and SQLite
- Pydantic
- Pytest and `httpx2` for API tests

## Requirements

- Python 3.10 or newer (the development environment currently uses Python 3.14.2)
- The packages listed in `requirements.txt`
- SQLite, which is included with Python

## Set up and run

From the project root, create and activate a virtual environment, then install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the development server:

```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/` to see the welcome response, or visit `http://127.0.0.1:8000/docs` to explore the API documentation.

The SQLite file `taskflow.db` is created in the current working directory when the application starts.

## Run tests

With the virtual environment activated, run:

```bash
pytest
```

## Database foundation

The application uses a SQLite database file named `taskflow.db` in the project directory. When the application starts, SQLAlchemy creates the tables if they do not already exist.

The `Task` model has these fields:

- `id`: integer primary key, assigned by the database.
- `title`: required task title.
- `description`: optional details about the task.
- `status`: `pending`, `in_progress`, or `completed`; defaults to `pending`.
- `priority`: `low`, `medium`, or `high`; defaults to `medium`.
- `due_date`: optional date by which the task should be completed.
- `created_at`: timestamp set when the row is created.
- `updated_at`: timestamp set when the row is created and refreshed when it changes.

FastAPI's `get_db` dependency opens a SQLAlchemy session for a request and closes it when the request is finished, including if an error occurs. ORM queries are used to read and write task rows.

## Task API

All task endpoints use the SQLAlchemy session dependency and Pydantic schemas. Invalid request bodies (including unsupported status/priority values and invalid dates) receive `422 Unprocessable Entity`. A task ID that does not exist receives `404 Not Found` with `{"detail":"Task not found"}`.

Titles are required and must contain at least one non-whitespace character. Invalid dates or enum values receive `422 Unprocessable Entity`. A well-formed integer ID that does not exist receives `404 Not Found`; a non-integer ID receives `422 Unprocessable Entity`. Validation gives clients a clear error instead of letting invalid values reach database operations.

| Method | Endpoint | Purpose | Success response |
| --- | --- | --- | --- |
| `GET` | `/` | Health/welcome response | `200 OK` |
| `POST` | `/tasks` | Create a task | `201 Created` |
| `GET` | `/tasks` | List tasks; optionally filter by `status` and/or `priority` | `200 OK` |
| `GET` | `/tasks/{task_id}` | Retrieve one task | `200 OK` |
| `PUT` | `/tasks/{task_id}` | Replace a task's editable fields | `200 OK` |
| `DELETE` | `/tasks/{task_id}` | Delete a task | `204 No Content` |

Task request validation failures return `422 Unprocessable Entity`. A valid but nonexistent task ID returns `404 Not Found`.

### Create a task

`POST /tasks` validates a task body, saves it, and returns `201 Created` with the created task:

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Prepare portfolio","description":"Finish the API","status":"in_progress","priority":"high","due_date":"2026-11-01"}'
```

Example response:

```json
{
  "id": 1,
  "title": "Prepare portfolio",
  "description": "Finish the API",
  "status": "in_progress",
  "priority": "high",
  "due_date": "2026-11-01",
  "created_at": "2026-10-18T17:00:00",
  "updated_at": "2026-10-18T17:00:00"
}
```

`status` defaults to `pending`, `priority` defaults to `medium`, and `description` and `due_date` are optional.

### List tasks

`GET /tasks` returns all tasks ordered by ID with `200 OK`. An empty database returns an empty list. Optional query parameters filter the results:

- `status` accepts `pending`, `in_progress`, or `completed`.
- `priority` accepts `low`, `medium`, or `high`.

You can provide either filter on its own or combine both. When combined, a task must match both values.

```bash
curl http://127.0.0.1:8000/tasks
curl "http://127.0.0.1:8000/tasks?status=pending"
curl "http://127.0.0.1:8000/tasks?priority=high"
curl "http://127.0.0.1:8000/tasks?status=pending&priority=high"
```

Query parameters are values added after `?` in the URL; `&` separates multiple parameters. FastAPI validates them against the task enums before the route runs. Unknown status or priority values receive `422 Unprocessable Entity` rather than silently returning misleading results. The route builds a SQLAlchemy ORM query and adds a filter only for each supplied parameter.

Example response:

```json
[
  {
    "id": 1,
    "title": "Prepare portfolio",
    "description": "Finish the API",
    "status": "in_progress",
    "priority": "high",
    "due_date": "2026-11-01",
    "created_at": "2026-10-18T17:00:00",
    "updated_at": "2026-10-18T17:00:00"
  }
]
```

### Retrieve one task

`GET /tasks/{task_id}` returns one task with `200 OK`, or `404 Not Found` if that ID does not exist.

```bash
curl http://127.0.0.1:8000/tasks/1
```

### Replace a task

`PUT /tasks/{task_id}` updates an existing task and returns the updated task with `200 OK`. Send the complete editable representation: `title` is required, and omitted optional fields use the same defaults as task creation. An unknown ID returns `404 Not Found`.

```bash
curl -X PUT http://127.0.0.1:8000/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"title":"Finish portfolio","description":"Polish the API","status":"completed","priority":"medium","due_date":null}'
```

The response has the same shape as the task response shown for creation.

### Delete a task

`DELETE /tasks/{task_id}` removes the task and returns `204 No Content` with an empty response body. An unknown ID returns `404 Not Found`.

```bash
curl -i -X DELETE http://127.0.0.1:8000/tasks/1
```

### Health check

The existing `GET /` welcome endpoint remains available and returns `200 OK`:

```json
{"message":"Welcome to TaskFlow API"}
```

## Known limitations

- There is no authentication or authorization; anyone who can reach the API can manage its tasks.
- The API has no pagination or sorting controls beyond the default task ID order.
- `PUT` replaces all editable fields; it is not a partial update endpoint.
- Tables are created automatically with SQLAlchemy `create_all`; schema migrations are not configured.
- The SQLite database path is fixed relative to the process's current working directory.