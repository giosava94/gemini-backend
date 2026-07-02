# GitHub Copilot Instructions for Gemini Backend

## Project Overview

Gemini Backend is a FastAPI REST service that manages accelerator beam line configurations using a Neo4j graph database.

- `app/` contains the application code
- `app/main.py` defines the FastAPI app entrypoint
- `app/config.py`, `app/db.py`, and `app/dependencies.py` handle configuration, database setup, and dependency injection
- `app/routers/` defines API routes for beam lines, line items, items, adjacencies, and connections
- `app/schemas/` defines Pydantic models for request/response validation
- `tests/` contains pytest-based tests for endpoints and application behavior

## Coding Conventions

- Use Python 3.12+ syntax and typing conventions
- Follow FastAPI idioms: routers, dependencies, Pydantic models, and response validation
- Keep business logic in routers and service-like functions, and schema definitions in `app/schemas/`
- Use `snake_case` for variables and functions, `CamelCase` only for Pydantic model classes
- Keep imports grouped and ordered: standard library, third-party, local application imports
- Maintain consistent formatting with `ruff` and use `ruff check .` to validate

## Test Framework

- Tests use `pytest`
- Test files live under `tests/` and follow the `test_*.py` naming convention
- Use fixtures from `tests/conftest.py` when available
- Run tests with:
  ```bash
  pytest tests/
  ```
- For coverage reporting:
  ```bash
  pytest --cov=app --cov-report=term-missing tests/
  ```

## Build and Run

### Dependency Installation

Preferred workflow is Poetry:
```bash
poetry install
```

Alternatively, use pip with the exported requirements:
```bash
pip install -r requirements.txt
```

For development dependencies:
```bash
poetry install --with dev
```

### Running Locally

The application depends on a running Neo4j instance. Use the provided compose files for local development.

```bash
docker compose -f compose.neo4j.dev.yml -f compose.dev.yml up
```

Or run the app directly with Uvicorn after installing dependencies:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Configuration

Use environment variables or a `.env` file in the project root:

- `NEO4J_URI` (default: `bolt://localhost:7687`)
- `NEO4J_USER` (default: `neo4j`)
- `NEO4J_PASSWORD` (default: `password`)
- `LOG_LEVEL` (default: `INFO`)

### Verification

Health check endpoint:
```bash
curl http://127.0.0.1:8000/api/v1/health
```

Interactive API docs are available at:

```
http://127.0.0.1:8000/docs
```
