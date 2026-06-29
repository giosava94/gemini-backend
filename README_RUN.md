# Running Locally

Instructions for running the Gemini Backend outside of Docker.

## Prerequisites

- Python 3.12+
- A running Neo4j instance (see below)
- `pip` or `poetry`

## 1. Start Neo4j

The easiest option is Docker:

```bash
docker compose -f compose.neo4j.dev.yml up
```

This starts Neo4j with:
- Bolt on `localhost:7687`
- HTTP browser on `http://localhost:7474`
- Authentication disabled (`NEO4J_AUTH=none`)
- Data persisted in Docker volumes `test-db-data` / `test-db-logs`

Or point `NEO4J_URI` at any existing Neo4j 5+ instance.

## 2. Install Dependencies

Using pip:

```bash
pip install -r requirements.txt
```

Using Poetry:

```bash
poetry install
```

For development tools (linting, tests):

```bash
pip install -r requirements.dev.txt
# or
poetry install --with dev
```

## 3. Configure Environment

Create a `.env` file in the project root, or export variables directly:

```bash
# .env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
LOG_LEVEL=INFO
```

| Variable         | Default                 | Description                                         |
|------------------|-------------------------|-----------------------------------------------------|
| `NEO4J_URI`      | `bolt://localhost:7687` | Neo4j Bolt URI                                      |
| `NEO4J_USER`     | `neo4j`                 | Neo4j username                                      |
| `NEO4J_PASSWORD` | `password`              | Neo4j password                                      |
| `LOG_LEVEL`      | `INFO`                  | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`      |

## 4. Run the Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The `--reload` flag enables auto-reload on file changes (development only).

The app will:
1. Connect to Neo4j and verify connectivity
2. Create uniqueness constraints on `BeamLine.name`, `LineItem.name`, and `Item.name`
3. Start serving on `http://127.0.0.1:8000`

## 5. Verify

Health check:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Expected response when healthy:

```json
{
  "status": "HEALTHY",
  "details": { "message": "Service is running" },
  "timestamp": "2026-01-01T00:00:00Z"
}
```

Interactive API docs (Swagger UI):

```
http://127.0.0.1:8000/docs
```

## 6. Running Tests

```bash
pytest tests/
```

With coverage:

```bash
pytest --cov=app --cov-report=term-missing tests/
```

## 7. Linting

```bash
ruff check .
```

Auto-fix:

```bash
ruff check --fix .
```

## Docker Build (Manual)

To build and run the container image directly:

```bash
docker build -t gemini-backend .
docker run -p 8000:8000 \
  -e NEO4J_URI=bolt://host.docker.internal:7687 \
  -e NEO4J_USER=neo4j \
  -e NEO4J_PASSWORD=password \
  gemini-backend
```

The container runs as a non-root user (`app`) and exposes port `8000`.  
The number of Uvicorn workers can be tuned via the `UVICORN_WORKERS` environment variable (default: `1`).
