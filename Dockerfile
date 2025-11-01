# Base image: Debian-derived Python for compatibility with FreeCAD packages.
FROM python:3.10-slim

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    POETRY_VERSION=1.8.3 \
    APP_HOME=/app

# Install system dependencies including FreeCAD and required libraries.
# We prefer the distro package over the AppImage here because it bundles
# the headless FreeCAD Python modules (`freecadcmd`, libFreeCAD) with
# correct ABI linkage for Debian, while keeping the container lean.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    freecad \
    freecad-python3 \
    libglu1-mesa \
    libsm6 \
    libxrender1 \
    libxext6 \
    wget \
    curl \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# FreeCAD installs its Python modules under /usr/lib/freecad/lib; expose this
# so `import FreeCAD` works inside Poetry-managed environments.
ENV PYTHONPATH=/usr/lib/freecad/lib:/app/src

# Install Poetry in the global interpreter so we can use it in entrypoints.
RUN pip install "poetry==$POETRY_VERSION"

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

# Make the entrypoint script executable
RUN chmod +x /usr/local/bin/entrypoint.sh

# Expose FastAPI default port for local dev / deployment
EXPOSE 8000

# Default entrypoint
ENTRYPOINT ["entrypoint.sh"]
