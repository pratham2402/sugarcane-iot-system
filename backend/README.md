# Cloud Backend

FastAPI-based cloud backend for receiving and serving sugarcane field telemetry data.

## Overview

The backend provides:
- **Telemetry ingestion API** — receives data from Raspberry Pi gateways
- **Query APIs** — retrieve readings by node, time range, or latest
- **Node management** — automatic node registration and tracking
- **OpenAPI documentation** — auto-generated at `/docs`

## Quick Start

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python -m app.main

# API available at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/telemetry/ingest` | Ingest single telemetry reading |
| `POST` | `/telemetry/ingest/batch` | Ingest batch of readings |
| `GET` | `/nodes` | List all registered nodes |
| `GET` | `/nodes/{node_id}` | Get specific node details |
| `GET` | `/latest-readings` | Latest reading per node |
| `GET` | `/readings` | Query readings with filters |

## Example Requests

### Ingest Telemetry
```bash
curl -X POST http://localhost:8000/telemetry/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "node-01",
    "timestamp": 1711929600,
    "firmware_version": "1.0.0",
    "battery_voltage": 3.72,
    "status": "ok",
    "readings": {
      "soil_moisture": {"value": 62.5, "unit": "%", "valid": true},
      "soil_temperature": {"value": 28.3, "unit": "°C", "valid": true}
    }
  }'
```

### Query Latest Readings
```bash
curl http://localhost:8000/latest-readings
```

### Query by Node and Time Range
```bash
curl "http://localhost:8000/readings?node_id=node-01&start=1711929000&end=1711930000&limit=50"
```

## Seed Test Data

```bash
python scripts/seed_test_data.py
```

## Testing

```bash
pip install pytest httpx
python -m pytest tests/ -v
```

## Architecture

```
app/
├── main.py              # FastAPI app factory + CLI entry
├── api/
│   ├── health.py        # GET /health
│   ├── telemetry.py     # POST /telemetry/ingest[/batch]
│   ├── nodes.py         # GET /nodes[/{id}]
│   └── readings.py      # GET /latest-readings, /readings
├── models/
│   ├── schemas.py       # Pydantic request/response models
│   └── database.py      # SQLAlchemy placeholder
├── db/
│   ├── connection.py    # SQLite connection + schema
│   └── repository.py    # Data access layer (repository pattern)
└── utils/
    └── validators.py    # Validation helpers
```

## Database

SQLite for MVP. The repository pattern (`repository.py`) isolates all SQL,
making it straightforward to swap to PostgreSQL:

1. Install `psycopg2` or `asyncpg`
2. Update `connection.py` with PostgreSQL driver
3. Adjust SQL syntax in `repository.py` (minimal changes needed)
4. Update `backend_config.yaml` with PostgreSQL URL

## Configuration

Edit `config/backend_config.yaml`:
- `server.host` / `server.port` — Bind address
- `database.url` — Database connection string
- `api.max_batch_size` — Maximum batch ingestion size
