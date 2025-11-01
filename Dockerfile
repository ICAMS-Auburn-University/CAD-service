FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    POETRY_VERSION=1.8.3 \
    APP_HOME=/app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        freecad \
        libglu1-mesa \
        libgl1-mesa-glx \
        libsm6 \
        libxrender1 \
        libxext6 \
        wget \
        curl \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==$POETRY_VERSION"

WORKDIR ${APP_HOME}

COPY pyproject.toml poetry.lock ${APP_HOME}/

RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

COPY src ${APP_HOME}/src
COPY tests ${APP_HOME}/tests
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["entrypoint.sh"]
