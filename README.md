# CAD Service

Headless microservice that ingests STEP/IGES CAD files, splits them into individual parts with FreeCAD, and uploads the results to Supabase Storage for order fulfillment workflows. The service runs as a long-lived HTTP API so it can be orchestrated alongside other platform services.

## Features

- Imports STEP/IGES files in headless mode via FreeCAD.
- Splits assemblies into individual bodies and exports each part.
- Uploads the original file and all generated parts to Supabase Storage under `cad-files/{userid}/{orderid}/`.
- Exposes a `/api/split` HTTP endpoint for orchestration systems.

## Project Layout

```
CAD-service/
├── pyproject.toml
├── poetry.lock
├── README.md
├── Dockerfile
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py
│   │   └── routes.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── split.py
│   ├── app.py
│   ├── splitter.py
│   ├── storage.py
│   ├── workflow.py
│   └── config.py
├── tests/
│   └── test_splitter.py
└── scripts/
    └── entrypoint.sh
```

## Requirements

- Docker
- Supabase instance with a storage bucket (configured via environment variables below)
- FreeCAD is installed inside the container (provided by the Dockerfile)

If you are running locally without Docker, FreeCAD must be installed and importable in the Python environment.

## Configuration

The service reads configuration from environment variables:

| Variable                    | Description                                                |
| --------------------------- | ---------------------------------------------------------- |
| `SUPABASE_URL`              | Supabase project URL                                       |
| `SUPABASE_KEY`              | Supabase API key (service or anon key with storage access) |
| `STORAGE_BUCKET`            | Supabase storage bucket used for CAD files                 |
| `STORAGE_PREFIX`            | Optional prefix (defaults to `cad-files`)                  |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional service-role key for future enhancements          |
| `CAD_SERVICE_LOG_LEVEL`     | Optional log level override (`INFO`, `DEBUG`, etc.)        |

## Docker Usage

Build the image:

```bash
docker build -t cad-service .
```

Run the service:

```bash
docker run --rm \
  -p 8000:8000 \
  --env SUPABASE_URL \
  --env SUPABASE_KEY \
  --env STORAGE_BUCKET \
  cad-service
```

With your variables already exported in the current shell, Docker will forward them. For an ad-hoc
command (for example, validating FreeCAD availability), reuse the same pattern:

```bash
docker run --rm \
  --env SUPABASE_URL \
  --env SUPABASE_KEY \
  --env STORAGE_BUCKET \
  cad-service \
  python -c "import FreeCAD, sys; print(sys.executable, FreeCAD.Version())"
```

Send a request with an uploaded CAD file:

```bash
curl -X POST "http://localhost:8000/api/split" \
  -F user_id=1234 \
  -F order_id=5678 \
  -F cad_file=@/path/to/assembly.step
```

The API responds with JSON describing the uploaded files:

```json
{
  "data": {
    "user_id": "1234",
    "order_id": "5678",
    "original": "cad-files/1234/5678/original.step",
    "parts": [
      "cad-files/1234/5678/parts/part_1.step",
      "cad-files/1234/5678/parts/part_2.step"
    ]
  }
}
```

If FreeCAD is not installed in the runtime environment, the endpoint responds with HTTP 503 and a
message indicating the dependency is missing.

The container continues running so upstream systems can post multiple jobs over time.

## Local Development

1. Install Poetry (https://python-poetry.org).
2. Install dependencies:
   ```bash
   poetry install
   ```
3. Run tests:
   ```bash
   poetry run pytest
   ```
4. Run the API locally:
   ```bash
   poetry run uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```

> Note: Regenerate the dependency lockfile with `poetry lock` whenever dependencies change.

### Future Enhancements

- Add job queue ingestion (Supabase Functions, MQ) in addition to HTTP.
- Generate signed URLs for uploaded parts to aid the bidding workflow.
- Include richer metadata (mass, volume, bounding boxes) per part for pricing logic.
