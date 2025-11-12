# CAD Service

Headless FastAPI microservice that ingests STEP assemblies, splits them into hierarchical STEP parts with FreeCAD, and uploads every artifact to Supabase Storage. The API now shells out to the existing `scripts/split_stp.py` helper via `/usr/bin/python3`, keeping FreeCAD work isolated from the web process.

## Features

- Handles STEP uploads via `/api/v1/split`.
- Saves the upload to a secure temp directory and runs `scripts/split_stp.py` with `/usr/bin/python3`.
- Recursively collects every generated STEP part (mirrors the FreeCAD group hierarchy).
- Uploads the original assembly plus each STEP part to Supabase (`{bucket}/{user}/{order}/parts/...`).
- Returns per-part metadata (name, hierarchy, storage path) for downstream apps.

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

| Variable                    | Description                                                      |
| --------------------------- | ---------------------------------------------------------------- |
| `SUPABASE_PROJECT_URL`      | Supabase project URL                                             |
| `SUPABASE_API_KEY`          | Supabase service/anon key with storage + bucket write access     |
| `SUPABASE_STORAGE_BUCKET`   | Supabase bucket name (e.g., `cad-files`)                         |
| `SYSTEM_PYTHON_PATH` (opt.) | Override for the Python executable used to run `split_stp.py`    |
| `SPLITTER_TIMEOUT_SECONDS`  | Optional timeout override for the splitter subprocess (default 900) |

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

## Splitter CLI

The API shells out to `scripts/split_stp.py` directly. You can exercise it inside the container:

```bash
/usr/bin/python3 scripts/split_stp.py \
  --input sandbox/Rocky_House.stp \
  --outdir sandbox/parts
```

The command mirrors what the FastAPI endpoint executes for every upload.

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
    "original": "cad-files/1234/5678/original/assembly_1a2b.stp",
    "parts": [
      {
        "name": "Little_Roof",
        "hierarchy": ["Roof"],
        "storage_path": "cad-files/1234/5678/parts/Roof/Little_Roof/Little_Roof.stp"
      }
    ]
  }
}
```

If FreeCAD fails, the API responds with HTTP 500 and the container logs show the exact error captured from the splitter subprocess.

### STEP File Examples

Grab public assemblies for testing from <https://www.steptools.com/docs/stpfiles/bigassy/index.html>.
