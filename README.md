# CAD Service

Headless microservice that ingests STEP/IGES CAD files, splits them into individual parts with FreeCAD, and uploads the results to Supabase Storage for order fulfillment workflows.

## Features
- Imports STEP/IGES files in headless mode via FreeCAD.
- Splits assemblies into individual bodies and exports each part.
- Uploads the original file and all generated parts to Supabase Storage under `cad-files/{userid}/{orderid}/`.
- CLI-first design, ready to be swapped for an HTTP interface in the future.

## Project Layout
```
CAD-service/
├── pyproject.toml
├── poetry.lock
├── README.md
├── Dockerfile
├── src/
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

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase API key (service or anon key with storage access) |
| `STORAGE_BUCKET` | Supabase storage bucket used for CAD files |
| `STORAGE_PREFIX` | Optional prefix (defaults to `cad-files`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional service-role key for future enhancements |

## Docker Usage
Build the image:
```bash
docker build -t cad-service .
```

Run a job:
```bash
docker run --rm \
  -v /path/to/cad-data:/data \
  -e SUPABASE_URL="https://xyzcompany.supabase.co" \
  -e SUPABASE_KEY="your-key" \
  -e STORAGE_BUCKET="cad-files" \
  cad-service \
  --userid 1234 \
  --orderid 5678 \
  --input /data/assembly.step
```

The CLI prints JSON describing the uploaded files:
```json
{
  "user_id": "1234",
  "order_id": "5678",
  "original": "cad-files/1234/5678/original.step",
  "parts": [
    "cad-files/1234/5678/parts/part_1.step",
    "cad-files/1234/5678/parts/part_2.step"
  ]
}
```

The container terminates after completing the job so it can be queued by orchestration systems.

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

> Note: `poetry.lock` is provided as a placeholder. Run `poetry lock` to regenerate a full lockfile once Poetry is installed locally.

### Future Enhancements
- Expose an HTTP or message-queue interface instead of CLI.
- Generate signed URLs for uploaded parts to aid the bidding workflow.
- Include richer metadata (mass, volume, bounding boxes) per part for pricing logic.
