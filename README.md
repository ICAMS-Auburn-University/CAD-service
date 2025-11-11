# CAD Service

Headless FastAPI microservice that ingests STEP/IGES CAD files, splits assemblies into individual parts with FreeCAD, generates DXF drawings, and uploads everything to Supabase Storage. FreeCAD is invoked directly from the API code (no CLI wrappers), so each request saves the upload, runs the splitter in-process, and immediately uploads the resulting STEP/DXF pairs.

## Features

- Handles STEP/IGES uploads via `/api/v1/split`.
- Uses FreeCAD directly from Python to recursively split assemblies (same logic as the validated script).
- Generates DXF drawings for each STEP part using pythonOCC/ezdxf.
- Uploads the original assembly plus every STEP/DXF pair to Supabase (`cad-files/{user}/{order}/...`).
- Returns a hierarchical layout tree so the frontend can render the assembly structure.

## Repository Layout

```
CAD-service/
├── Dockerfile
├── requirements.txt
├── README.md
├── scripts/
│   └── entrypoint.sh
├── src/
│   ├── api/
│   ├── cad/
│   ├── models/
│   └── app.py
└── tests/
```

## Configuration

Set these variables in `.env` and pass them to `docker run --env-file .env …`:

| Variable                  | Description                                               |
| ------------------------- | --------------------------------------------------------- |
| `SUPABASE_PROJECT_URL`    | Supabase project URL                                      |
| `SUPABASE_API_KEY`        | Supabase service/anon key with storage access             |
| `SUPABASE_STORAGE_BUCKET` | Supabase bucket name (e.g., `cad-files`)                  |
| `SUPABASE_STORAGE_PREFIX` | Optional prefix under the bucket (defaults to `cad-files`)|
| `CAD_SERVICE_LOG_LEVEL`   | Optional log level (`INFO`, `DEBUG`, etc.)                |

## Local Development (inside Docker)

1. Build the image:
   ```bash
   docker build -t cad-service-dev .
   ```

2. Start a development container:
   ```bash
   docker run --rm -it \
     -p 8000:8000 \
     --env-file .env \
     -v "$(pwd)":/app \
     cad-service-dev /bin/bash
   ```
   Always run the API from inside this shell so FreeCAD/pythonOCC are available.

3. Launch FastAPI:
   ```bash
   python -m uvicorn app:app --app-dir src --host 0.0.0.0 --port 8000 --reload
   ```

4. Run tests:
   ```bash
   pytest
   ```

5. One-off commands without an interactive shell:
   ```bash
   docker run --rm \
     --env-file .env \
     -v "$(pwd)":/app \
     cad-service-dev \
     bash -lc "pytest"
   ```

## Running the packaged service

```bash
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  cad-service-dev
```

Sanity-check FreeCAD inside the container:

```bash
docker run --rm \
  --env-file .env \
  cad-service-dev \
  python -c "import FreeCAD, sys; print(sys.executable, FreeCAD.Version())"
```

## API Usage

```bash
curl -X POST "http://localhost:8000/api/v1/split" \
  -F user_id=1234 \
  -F order_id=5678 \
  -F cad_file=@/path/to/assembly.step
```

Example response:

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

If FreeCAD fails, the API responds with HTTP 500 and the container logs show the exact error from the splitter subprocess.

### STEP File Examples

Grab public assemblies for testing from <https://www.steptools.com/docs/stpfiles/bigassy/index.html>.
