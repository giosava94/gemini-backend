# Gemini Backend

A FastAPI REST backend for managing accelerator beam line configurations, backed by a Neo4j graph database.

## Overview

The service models the physical layout of particle accelerator beam lines as a graph:

- **BeamLines** — top-level accelerator beam lines
- **LineItems** — elements along a beam line (magnets, diagnostics, valves, etc.)
- **Items** — standalone non-line components (racks, pumps, flanges, etc.)

Relationships between nodes capture adjacency (Previous/Next along a beam line) and arbitrary connections between any two items.

## Requirements

- Python 3.12+
- Neo4j (tested with `neo4j:2026` image)
- [Poetry](https://python-poetry.org/) for dependency management (or use the exported `requirements.txt`)

## Quick Start with Docker Compose

The easiest way to run the full stack is with Docker Compose. Two compose files are provided and must be used together:

```bash
docker compose -f compose.neo4j.dev.yml -f compose.dev.yml up
```

- `compose.neo4j.dev.yml` — starts a Neo4j instance on ports `7687` (Bolt) and `7474` (HTTP browser)
- `compose.dev.yml` — builds and starts the FastAPI application on port `8000`

The app waits for Neo4j to be healthy before starting.

## Configuration

Configuration is loaded from environment variables or a `.env` file in the project root:

| Variable         | Default                 | Description                                         |
| ---------------- | ----------------------- | --------------------------------------------------- |
| `NEO4J_URI`      | `bolt://localhost:7687` | Neo4j Bolt connection URI                           |
| `NEO4J_USER`     | `neo4j`                 | Neo4j username                                      |
| `NEO4J_PASSWORD` | `password`              | Neo4j password                                      |
| `LOG_LEVEL`      | `INFO`                  | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## API Endpoints

All endpoints are prefixed with `/api/v1`.

### Health

| Method | Path             | Description          |
| ------ | ---------------- | -------------------- |
| GET    | `/api/v1/health` | Service health check |

### Beam Lines

| Method | Path                      | Description                        |
| ------ | ------------------------- | ---------------------------------- |
| POST   | `/api/v1/beam-lines`      | Create a beam line                 |
| GET    | `/api/v1/beam-lines`      | List beam lines (paginated)        |
| GET    | `/api/v1/beam-lines/{id}` | Get a specific beam line           |
| PATCH  | `/api/v1/beam-lines/{id}` | Update a beam line                 |
| DELETE | `/api/v1/beam-lines/{id}` | Delete a beam line (`?force=true`) |

### Line Items

| Method | Path                                           | Description                             |
| ------ | ---------------------------------------------- | --------------------------------------- |
| POST   | `/api/v1/beam-lines/{beam_id}/line-items`      | Create a line item under a beam line    |
| GET    | `/api/v1/beam-lines/{beam_id}/line-items`      | List line items (paginated, filterable) |
| GET    | `/api/v1/beam-lines/{beam_id}/line-items/{id}` | Get a specific line item                |
| PATCH  | `/api/v1/beam-lines/{beam_id}/line-items/{id}` | Update a line item                      |
| DELETE | `/api/v1/beam-lines/{beam_id}/line-items/{id}` | Delete a line item (`?force=true`)      |

### Line Item Adjacents

| Method | Path                                                              | Description                                       |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------- |
| GET    | `/api/v1/beam-lines/{beam_id}/line-items/{id}/adjacents`          | List adjacent items (Previous/Next)               |
| PUT    | `/api/v1/beam-lines/{beam_id}/line-items/{id}/adjacents`          | Add adjacent items                                |
| DELETE | `/api/v1/beam-lines/{beam_id}/line-items/{id}/adjacents`          | Remove adjacent items                             |
| PATCH  | `/api/v1/beam-lines/{beam_id}/line-items/{id}/adjacents/{adj_id}` | Update position/index of a specific adjacent item |

### Line Item Connections

| Method | Path                                                       | Description                                                             |
| ------ | ---------------------------------------------------------- | ----------------------------------------------------------------------- |
| GET    | `/api/v1/beam-lines/{beam_id}/line-items/{id}/connections` | List connected non-line items                                           |
| PUT    | `/api/v1/beam-lines/{beam_id}/line-items/{id}/connections` | Add connections to non-line items with optional relationship properties |
| DELETE | `/api/v1/beam-lines/{beam_id}/line-items/{id}/connections` | Remove connections from non-line items                                  |

### Items (Non-Line)

| Method | Path                 | Description                        |
| ------ | -------------------- | ---------------------------------- |
| POST   | `/api/v1/items`      | Create a non-line item             |
| GET    | `/api/v1/items`      | List items (paginated, filterable) |
| GET    | `/api/v1/items/{id}` | Get a specific item                |
| PATCH  | `/api/v1/items/{id}` | Update an item                     |
| DELETE | `/api/v1/items/{id}` | Delete an item (`?force=true`)     |

### Item Connections

| Method | Path                                       | Description                                                          |
| ------ | ------------------------------------------ | -------------------------------------------------------------------- |
| GET    | `/api/v1/items/{id}/connections`           | List items connected to this item                                    |
| PUT    | `/api/v1/items/{id}/connections`           | Add connections to other items with optional relationship properties |
| DELETE | `/api/v1/items/{id}/connections`           | Remove connections                                                   |
| GET    | `/api/v1/items/{id}/line-item-connections` | List beam line items connected to this item                          |

## Data Models

### LineItem kinds

`Diagnostic`, `ES Triplet`, `ES Steerer`, `ES Dipole`, `ES Quadrupole`, `ES Multipole`, `MG Triplet`, `MG Steerer`, `MG Dipole`, `MG Solenoid`, `Valve Gate`, `High Energy Buncher`, `Low Energy Buncher`, `Radiofrequency Quadrupole`, `Cryostat`, `Charge Breeder`, `Beam Cooler`, `Tape Station`, `Ion Source`, `Target Ion Source`, `Wien Filter`

### LineItem statuses

`0` = Enabled, `1` = Disabled, `2` = Maintenance

### Item kinds

`MTBX`, `Rack`, `BACCO`, `Primary_Pump`, `Turbomolecular_Pump`, `Flange`, `Line`, `Box`

### Item statuses

`0` = Active, `1` = Unmounted, `2` = Maintenance, `3` = Dismitted

## Development

Install dev dependencies:

```bash
poetry install
```

Run linting:

```bash
ruff check .
```

Run tests:

```bash
pytest --cov=app tests/
```

See [README_RUN.md](README_RUN.md) for running the app locally without Docker.

## License

EUPL v1.2 — © Giovanni Savarese, INFN-LNL
