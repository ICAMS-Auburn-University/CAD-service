FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    POETRY_VERSION=1.8.3 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Install FreeCAD and essential system dependencies
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
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set PYTHONPATH so Python can find FreeCAD modules
ENV PYTHONPATH=/usr/lib/freecad-python3/lib:/app/src

# Install Poetry
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Copy and install Python dependencies via Poetry
COPY pyproject.toml poetry.lock ${APP_HOME}/
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY src ${APP_HOME}/src
COPY tests ${APP_HOME}/tests
COPY scripts ${APP_HOME}/scripts

# Make entrypoint executable
RUN sed -i 's/\r$//' ${APP_HOME}/scripts/entrypoint.sh && \
    chmod +x ${APP_HOME}/scripts/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
