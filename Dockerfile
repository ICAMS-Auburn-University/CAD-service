FROM ubuntu:22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app \
    MINICONDA_VERSION=latest

WORKDIR ${APP_HOME}

# Install system packages needed by FreeCAD, pythonocc-core, rendering tools, build tools, and download utilities
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        libglu1-mesa \
        libsm6 \
        libxrender1 \
        libxext6 \
        inkscape \
        build-essential \
        curl \
        ca-certificates \
        && rm -rf /var/lib/apt/lists/*

# Download and install Miniconda (choose latest for max compatibility)
RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh && \
    bash /tmp/miniconda.sh -b -p /opt/conda && \
    rm /tmp/miniconda.sh
ENV PATH="/opt/conda/bin:$PATH"

# Accept Anaconda Terms of Service for default channels (required for Docker/CI from mid-2024)
RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# Fix libmamba conda solver bug and set classic solver for stability
RUN conda install -y conda libmamba libmambapy && conda config --set solver classic

# Install Python 3.10 and all core CAD/scientific libraries ONLY via conda (NO ezdxf; that's pip-only)
RUN conda install -y -c conda-forge \
        python=3.10 \
        freecad \
        pythonocc-core \
        numpy \
    && conda clean -afy

# Upgrade pip, then pip install all remaining requirements (ezdxf, fastapi, etc.)
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt ${APP_HOME}/
RUN pip install --no-cache-dir -r requirements.txt

COPY src ${APP_HOME}/src
COPY tests ${APP_HOME}/tests
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
