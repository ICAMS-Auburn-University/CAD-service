FROM continuumio/miniconda3:latest

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    QT_QPA_PLATFORM=offscreen \
    FREECAD_SELF_CONTAINED=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Install FreeCAD and system dependencies via apt (fast, pre-compiled, no Conda memory issues)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        freecad \
        freecad-python3 \
        libglu1-mesa \
        libffi-dev \
        libsm6 \
        libxrender1 \
        libxext6 \
        inkscape \
        wget \
        curl \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# FreeCAD installs its Python modules under /usr/lib/freecad/lib
ENV PYTHONPATH=/usr/lib/freecad/lib:/app/src
ENV LD_LIBRARY_PATH=/opt/conda/lib:${LD_LIBRARY_PATH}

# Accept Anaconda Terms of Service for default channels
RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# Install Python 3.10 and pythonocc-core via conda (much smaller solve than FreeCAD)
RUN conda install -y -c conda-forge libstdcxx-ng=13.1.0 python=3.10 pythonocc-core && conda clean -afy

# Upgrade pip and install all pure Python dependencies (ezdxf, fastapi, etc.)
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt ${APP_HOME}/
RUN pip install --no-cache-dir -r requirements.txt

# Sanity check: ensure FreeCAD modules are importable
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
