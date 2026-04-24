FROM python:3.12-slim

# Metadatos del TFG
LABEL maintainer="TFG Student"
LABEL description="OpenCTI Gemini Enrichment Connector"

# Variables para que Python no guarde caché y sea más rápido
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Crear un usuario seguro
RUN groupadd -r opencti && useradd -r -g opencti opencti

# Directorio de trabajo
WORKDIR /opt/opencti-connector-gemini

# Instalar dependencias básicas del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copiar y instalar librerías Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiar el código del conector
COPY . .

# Ajustar permisos para el usuario seguro
RUN chown -R opencti:opencti /opt/opencti-connector-gemini
USER opencti

# Comando de arranque
CMD ["python3", "gemini_connector.py"]
