# Use Python 3.10 slim base image
FROM python:3.10-slim

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    POETRY_VERSION=1.8.3 \
    APP_HOME=/app

# Install system dependencies including FreeCAD and required libraries
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    freecad \
    freecad-python3 \
    libglu1-mesa \
    libgl1-mesa-glx \
    libsm6 \
    libxrender1 \
    libxext6 \
    wget \
    curl \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install "poetry==$POETRY_VERSION"

# Set working directory
WORKDIR ${APP_HOME}

# Copy Poetry files first for caching
COPY pyproject.toml poetry.lock ${APP_HOME}/

# Configure Poetry to install dependencies in the global environment (not virtualenv), then install
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

# Copy application code
COPY src ${APP_HOME}/src
COPY tests ${APP_HOME}/tests
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh

# Make the entrypoint script executable
RUN chmod +x /usr/local/bin/entrypoint.sh

# Default entrypoint
ENTRYPOINT ["entrypoint.sh"]
