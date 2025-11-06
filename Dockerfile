FROM continuumio/miniconda3:latest

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
ENV PYTHONPATH=/usr/lib/freecad/lib:/app/src

# Install conda Python deps for pythonOCC and DXF export
RUN conda install -y -c conda-forge python=3.10 pythonocc-core ezdxf

# Poetry and cairosvg for existing workflow
RUN pip install "poetry==$POETRY_VERSION" cairosvg

WORKDIR ${APP_HOME}
COPY pyproject.toml poetry.lock ${APP_HOME}/

RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

# Sanity check: ensure FreeCAD modules are importable inside the container
RUN python - <<'PY'
import sys
print(f"Python executable: {sys.executable}")
import FreeCAD
print(f"FreeCAD version: {FreeCAD.Version()}")
PY

COPY src ${APP_HOME}/src
COPY tests ${APP_HOME}/tests
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && \
    chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
