# CAD Service

Headless microservice that ingests STEP/IGES CAD files, splits them into individual parts with FreeCAD, generates DXF drawings, and uploads the results to Supabase Storage. The service exposes a FastAPI endpoint so the CAD workflow can be orchestrated by the rest of the platform.

## Features

- Imports STEP/IGES files in headless FreeCAD mode.
- Recursively walks assemblies and exports STEP + DXF assets for every sub-part.
- Uploads the original file and per-part exports to Supabase under `cad-files/{user}/{order}/`.
- Returns a hierarchical layout JSON so the frontend can render the assembly tree.
- Ships as a Docker image that already contains FreeCAD, pythonOCC, and Poetry.

## Project Layout

```
CAD-service/
├── Dockerfile
├── pyproject.toml
├── README.md
├── scripts/
│   └── entrypoint.sh
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py
│   │   └── routes.py
│   ├── cad/
│   │   ├── __init__.py
│   │   ├── dxf.py
│   │   ├── layouts.py
│   │   ├── splitter.py
│   │   ├── storage.py
│   │   ├── types.py
│   │   └── workflow.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── split.py
│   ├── app.py
│   └── static/
└── tests/
    └── test_splitter.py
```

## Requirements

- Docker (local dev and prod always run inside the container).
- Supabase project with a storage bucket and API keys.
- Optional: `.env` file holding the required environment variables.

## Configuration

| Variable                    | Description                                                |
| --------------------------- | ---------------------------------------------------------- |
| `SUPABASE_URL`              | Supabase project URL                                       |
| `SUPABASE_KEY`              | Supabase API key (service or anon key with storage access) |
| `STORAGE_BUCKET`            | Supabase storage bucket for CAD files                      |
| `STORAGE_PREFIX`            | Optional prefix (defaults to `cad-files`)                  |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional service-role key for future enhancements          |
| `CAD_SERVICE_LOG_LEVEL`     | Optional log level override (`INFO`, `DEBUG`, etc.)        |

Set these in `.env` for local work and pass them to `docker run`/Compose in deployed environments.

## Local Development (Docker-only workflow)

1. **Build the dev image**

   ```bash
   docker build -t cad-service-dev .
   ```

2. **Start an interactive container with your source mounted**

   ```bash
   docker run --rm -it \
     -p 8000:8000 \
     --env-file .env \
     -v "$(pwd)":/app \
     cad-service-dev /bin/bash
   ```

   This drops you into `/app` with Poetry, FreeCAD, pythonOCC, and the repo mounted for hot reload.

3. **Run the API inside the container**

   ```bash
   poetry run uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Run tests inside the container**

   ```bash
   poetry run pytest
   ```

5. **Fire one-off commands without opening a shell**

   ```bash
   docker run --rm \
     --env-file .env \
     cad-service-dev \
     bash -lc "poetry run pytest"
   ```

## Running the packaged service

Once you’re ready to run the API without an interactive shell:

```bash
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  cad-service-dev
```

To sanity-check FreeCAD inside the container:

```bash
docker run --rm \
  --env-file .env \
  cad-service-dev \
  python -c "import FreeCAD, sys; print(sys.executable, FreeCAD.Version())"
```

## API usage

Send a split request with an uploaded CAD file:

```bash
curl -X POST "http://localhost:8000/api/split" \
  -F user_id=1234 \
  -F order_id=5678 \
  -F cad_file=@/path/to/assembly.step
```

Sample response:

```json
{
  "data": {
    "user_id": "1234",
    "order_id": "5678",
    "original": "cad-files/1234/5678/original.step",
    "parts": [
      {
        "name": "sub_build1",
        "hierarchy": ["main_build"],
        "step_path": "cad-files/1234/5678/parts/main_build/sub_build1/sub_build1.stp",
        "dxf_path": "cad-files/1234/5678/parts/main_build/sub_build1/sub_build1.dxf"
      }
    ],
    "layout": {
      "main_build": {
        "sub_build1": ["plate_a", "plate_b"],
        "_parts": ["sub_build2"]
      }
    }
  }
}
```

If FreeCAD is unavailable in the container the endpoint returns HTTP 503 with a descriptive error.

### STEP File Examples

You can grab public assemblies for testing here: <https://www.steptools.com/docs/stpfiles/bigassy/index.html>.
