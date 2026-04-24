FROM python:3.12-slim

# Metadata
LABEL maintainer="Manuel Araújo"
LABEL description="OpenCTI Multi-Feed Connector"
LABEL version="1.0.0"

#Variables entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

#Preparacion para evitar ejecutar como root
RUN groupadd -r opencti && useradd -r -g opencti opencti

#Directorio de trabajo
WORKDIR /opt/opencti-connector-multifeed

#Dependendcias sistema

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    git \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*


#Dependencias python
COPY requirements.txt .

# Actualizamos pip por seguridad e instalamos requisitos
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

#Copiamos todo al docker
COPY . .

#Permisos y sec
RUN chown -R opencti:opencti /opt/opencti-connector-multifeed
USER opencti

#Ejecuccion
CMD ["python3", "connector.py"]
