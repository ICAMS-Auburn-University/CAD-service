FROM python:3.10-slim

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    POETRY_VERSION=1.8.3 \
    APP_HOME=/app

# Install system dependencies including FreeCAD, Inkscape for SVG→DXF conversion
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    freecad \
    freecad-python3 \
    libglu1-mesa \
    libsm6 \
    libxrender1 \
    libxext6 \
    inkscape \
    wget \
    curl \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# FreeCAD installs its Python modules under /usr/lib/freecad/lib; expose this
# so `import FreeCAD` works inside Poetry-managed environments.
ENV PYTHONPATH=/usr/lib/freecad/lib:/app/src

# Install Poetry and cairosvg (for SVG to PNG conversion)
RUN pip install "poetry==$POETRY_VERSION" cairosvg

# Set working directory
WORKDIR ${APP_HOME}

# Copy Poetry files first for caching
COPY pyproject.toml poetry.lock ${APP_HOME}/

# Configure Poetry to install dependencies in the global environment (not virtualenv), then install
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

# Sanity check: ensure FreeCAD modules are importable inside the container.
RUN python - <<'PY'
import sys
print(f"Python executable: {sys.executable}")
import FreeCAD
print(f"FreeCAD version: {FreeCAD.Version()}")
PY

# Copy application code
COPY src ${APP_HOME}/src
COPY tests ${APP_HOME}/tests
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh

# Normalize line endings (handle CRLF checked-out on Windows) and make executable
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && \
    chmod +x /usr/local/bin/entrypoint.sh

# Expose FastAPI default port for local dev / deployment
EXPOSE 8000

# Default entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
