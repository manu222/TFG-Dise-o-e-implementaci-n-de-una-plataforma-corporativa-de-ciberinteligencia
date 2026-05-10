# Propósito y contexto

Este anexo documenta el conector **Multi-Feed**, uno de los tres conectores propios desarrollados para la plataforma OpenCTI del laboratorio. Su existencia y motivación se justifican en el apartado 3.2.2.B (Descripción técnica del despliegue) y su contribución a los resultados del proyecto se cuantifica en el apartado 3.6.2 (Plan de pruebas y casos de uso validados) de la memoria.
## Rol arquitectónico

El conector Multi-Feed cubre una carencia identificada en el ecosistema de conectores oficiales de OpenCTI: la ausencia de una pieza genérica capaz de ingerir simultáneamente fuentes con formatos heterogéneos (listas de IPs en texto plano, listas de URLs, JSON anidado de configuraciones) sin necesidad de mantener un conector separado por cada formato. En su lugar, este conector implementa **un único motor con tres parsers especializados** que se seleccionan  desde el fichero de configuración `feeds.json`, lo que permite añadir nuevas fuentes sin tocar el código del conector siempre que su formato encaje con uno de los tres parsers disponibles.
## Relación con otros componentes del laboratorio

- **OpenCTI**: el conector publica objetos STIX 2.1 contra la API GraphQL de la plataforma mediante el SDK `pycti`, integrándose como un servicio Docker más dentro del *compose* de la capa de Conectores documentada en el anexo *OpenCTI*.
- **opencti-control**: el ciclo de vida del contenedor (reconstrucción tras editar `connector.py` o `feeds.json`) se opera mediante el comando `opencti-control update-connectors` documentado en el anexo correspondiente, en lugar de invocar manualmente `docker compose`.

---
# Documentación Técnica: Conector OpenCTI Multi-Feed

**Proyecto:** TFG Ciberseguridad  
**Autor:** Manuel Araújo  
**Ruta:** `/opt/opencti/custom_connectors/multifeed`

---

## Tabla de Contenidos

1. [Descripción General](#1-descripción-general)
2. [Arquitectura y Estructura de Archivos](#2-arquitectura-y-estructura-de-archivos)
3. [Dependencias](#3-dependencias)
4. [Imagen Docker](#4-imagen-docker)
5. [Integración en el Docker Compose](#5-integración-en-el-docker-compose)
6. [Configuración de Fuentes (`feeds.json`)](#6-configuración-de-fuentes-feedsjson)
7. [Lógica del Conector (`connector.py`)](#7-lógica-del-conector-connectorpy)
8. [Parsers Disponibles](#8-parsers-disponibles)
9. [Validación y Seguridad](#9-validación-y-seguridad)
10. [Variables de Entorno](#10-variables-de-entorno)
11. [Ciclo de Vida de una Ejecución](#11-ciclo-de-vida-de-una-ejecución)
12. [Objetos STIX2 Generados](#12-objetos-stix2-generados)
13. [Añadir una Nueva Fuente](#13-añadir-una-nueva-fuente)
14. [Solución de Problemas](#14-solución-de-problemas)

---

## 1. Descripción General

El conector **Multi-Feed** es un conector de ingesta de amenazas personalizado para la plataforma [OpenCTI](https://www.opencti.io/). Su función es consultar periódicamente múltiples fuentes de inteligencia de amenazas (threat feeds) de forma automática, transformar los datos descargados en objetos **STIX 2.1** y publicarlos en OpenCTI para su análisis y correlación.

El conector se ejecuta como un servicio Docker independiente dentro del stack de conectores de OpenCTI (`/opt/opencti/connectors`) y se construye a partir del código fuente ubicado en `/opt/opencti/custom_connectors/multifeed`.

### Fuentes integradas (por defecto)

| Nombre | Tipo de dato | Parser |
|---|---|---|
| Cobalt Strike C2 (Drb-Ra) | IPs y dominios C2 en JSON | `drb-json` |
| PoshC2 (Drb-Ra) | IPs y dominios C2 en JSON | `drb-json` |
| OpenPhish Community | URLs de phishing (texto plano) | `text-list-url` |
| Tor Exit Nodes | IPs de nodos de salida Tor | `text-list-ip` |

---

## 2. Arquitectura y Estructura de Archivos

```
/opt/opencti/custom_connectors/multifeed/
├── connector.py          # Lógica principal del conector
├── feeds.json            # Declaración de las fuentes de inteligencia
├── requirements.txt      # Dependencias Python
└── Dockerfile            # Imagen Docker del conector
```

El Docker Compose de conectores (`/opt/opencti/connectors/docker-compose.yml`) referencia el directorio `multifeed` mediante un bloque `build:` apuntando a su contexto, lo que permite construir la imagen localmente sin necesidad de un registro externo.

---

## 3. Dependencias

Definidas en `requirements.txt`:

| Paquete | Versión | Función |
|---|---|---|
| `pycti` | `6.4.1` | SDK oficial de OpenCTI para conectores |
| `stix2` | `3.0.1` | Generación y serialización de objetos STIX 2.1 |
| `requests` | `>=2.32.0` | Descarga de feeds HTTP/HTTPS |
| `ipaddress` | `1.0.23` | Validación y clasificación de direcciones IP |

---

## 4. Imagen Docker

El `Dockerfile` define los siguientes pasos:

```
Base:      python:3.12-slim
WorkDir:   /opt/opencti-connector-multifeed
Usuario:   opencti (no-root, por seguridad)
EntryPoint: python3 connector.py
```

### Proceso de build

El Dockerfile ejecuta los siguientes pasos en orden:

1. Instala dependencias del sistema (`build-essential`, `curl`, `git`, `libmagic1`, `ca-certificates`).
2. Actualiza `pip` e instala las dependencias declaradas en `requirements.txt`.
3. Copia el código fuente al directorio de trabajo.
4. Ajusta permisos y cambia al usuario no privilegiado `opencti`.
5. Ejecuta `python3 connector.py` como punto de entrada del contenedor.

### Buenas prácticas aplicadas

- Ejecución como usuario no privilegiado (`opencti:opencti`).
- Variables de entorno que evitan bytecode y bufering (`PYTHONUNBUFFERED`, `PYTHONDONTWRITEBYTECODE`).
- Limpieza de caché de `apt` en la misma capa para reducir el tamaño de imagen.

---

## 5. Integración en el Docker Compose

El conector debe declararse como un servicio en el `docker-compose.yml` del directorio `/opt/opencti/connectors`. Ejemplo de bloque de servicio:

```yaml
connector-multifeed:
    build:
      context: ../custom_connectors/multifeed
    image: custom-connector-multifeed:latest
    environment:
      - OPENCTI_URL=http://opencti:8080
      - OPENCTI_TOKEN=${MULTIFEED_USER_TOKEN}
      - CONNECTOR_ID=${CONNECTOR_MULTIFEED_TOKEN}
      - CONNECTOR_TYPE=EXTERNAL_IMPORT
      - CONNECTOR_NAME=TFG Multi-Feed
      - CONNECTOR_SCOPE=malware,ipv4-addr,url,indicator
      - CONNECTOR_LOG_LEVEL=info
      - CONNECTOR_RUN_EVERY=14400
    restart: always
    networks:
      - opencti_net
```

>[!IMPORTANT] 
>`CONNECTOR_ID` debe ser un UUID v4 único

---

## 6. Configuración de Fuentes (`feeds.json`)

El archivo `feeds.json` es la **única pieza de configuración** que necesita modificarse para añadir, editar o deshabilitar fuentes. Se carga en tiempo de ejecución en cada ciclo.

### Estructura de cada entrada

```json
{
  "name": "Nombre descriptivo del feed",
  "url": "https://url-del-feed.com/datos.txt",
  "parser": "tipo-de-parser",
  "interval": 3600,
  "labels": ["etiqueta1", "etiqueta2"]
}
```

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `name` | string | ✅ | Nombre del feed (solo informativo) |
| `url` | string | ✅ | URL de descarga del feed |
| `parser` | string | ✅ | Tipo de parser a usar (ver sección 8) |
| `interval` | integer | ❌ | Intervalo sugerido en segundos (no usado internamente; el intervalo real lo controla `CONNECTOR_RUN_EVERY`) |
| `labels` | array | ✅ | Etiquetas STIX que se añaden a todos los objetos del feed |

### Feeds configurados actualmente

```json
[
  {
    "name": "Cobalt Strike C2 (Drb-Ra)",
    "url": "https://raw.githubusercontent.com/drb-ra/C2IntelFeeds/refs/heads/master/C2_configs/cobaltstrike-30day.json",
    "parser": "drb-json",
    "interval": 3600,
    "labels": ["cobalt-strike", "c2", "apt"]
  },
  {
    "name": "PoshC2 (Drb-Ra)",
    "url": "https://raw.githubusercontent.com/drb-ra/C2IntelFeeds/refs/heads/master/C2_configs/poshc2.json",
    "parser": "drb-json",
    "interval": 3600,
    "labels": ["poshc2", "c2"]
  },
  {
    "name": "OpenPhish Community",
    "url": "https://openphish.com/feed.txt",
    "parser": "text-list-url",
    "interval": 3600,
    "labels": ["phishing", "credential-theft"]
  },
  {
    "name": "Tor Exit Nodes",
    "url": "https://check.torproject.org/torbulkexitlist",
    "parser": "text-list-ip",
    "interval": 86400,
    "labels": ["tor", "anonymization", "darkweb"]
  }
]
```

---

## 7. Lógica del Conector (`connector.py`)

### Clase principal: `MultiFeedConnector`

El conector se inicializa con dos componentes clave:

- **`self.helper`**: Instancia de `OpenCTIConnectorHelper`, que gestiona la comunicación con la API de OpenCTI (logs, trabajos, envío de bundles).
- **`self.author`**: Objeto STIX `Identity` que actúa como autor de todos los indicadores creados. Se referencia en cada objeto mediante `created_by_ref`.

```
Identity:
  name: "TFG Threat Intelligence"
  identity_class: "organization"
  description: "Ingesta Automática - TFG Ciberseguridad"
```

### Método `run()` — Bucle principal

El conector opera en un bucle infinito con la siguiente lógica:

```
1. Obtener timestamp actual y crear un "trabajo" en OpenCTI (work_id)
2. Cargar feeds.json
3. Para cada feed:
   a. Descargar el contenido del URL (con timeout de 30s)
   b. Invocar el parser correspondiente
   c. Construir un Bundle STIX2 con los objetos resultantes
   d. Enviar el Bundle a OpenCTI (update=True para actualizar existentes)
4. Marcar el trabajo como completado
5. Dormir CONNECTOR_RUN_EVERY segundos (por defecto: 3600)
```
> [!NOTE] 
> Sobre `update=True`: la llamada `helper.send_stix2_bundle(bundle, update=True, work_id=work_id)` indica al SDK de OpenCTI que, si un objeto STIX ya existe en la base de datos (mismo `id`), debe actualizar sus campos (etiquetas, relaciones, score) en lugar de descartarlo silenciosamente. Esto es importante para el caso de uso típico del conector: una IP detectada hoy en *Cobalt Strike C2* y mañana en *PoshC2* enriquece su contexto con etiquetas de ambas familias, mostrando en el grafo de OpenCTI la relación con los dos malware.

---

## 8. Parsers Disponibles

### `drb-json` — Feeds de C2 (Repositorio github)

**Formato de entrada:** JSONL (un objeto JSON por línea)

**Campos extraídos:**
- `result.ip` → IP principal del servidor C2
- `result.C2Server` → Puede contener una IP secundaria, un dominio, o una lista

**Lógica de procesamiento:**

```
Para cada línea:
  1. Extraer IP → si es pública, crear IPv4Address + relación "related-to" con el Malware
  2. Extraer C2Server y limpiar el valor:
     a. Si C2Server es una lista → usar el primer elemento
     b. Eliminar todo lo que vaya después de ',' (separadores de puertos/params)
     c. Limpiar protocolo, paths y puertos con _clean_domain()
  3. Clasificar el C2Server limpio:
     - Si tiene estructura de IP:
         · Si es pública Y distinta a la IP principal → IPv4Address + relación
         · Si es privada/loopback (ej: 127.0.0.1) → IGNORAR (no se crea ningún objeto)
     - Si NO es una IP → crear DomainName + relación
  4. Crear un objeto Malware padre con el nombre derivado de la primera etiqueta
```

**Objetos STIX generados:**
- `Malware` (padre, uno por feed)
- `IPv4Address` + `Relationship` (related-to → Malware)
- `DomainName` + `Relationship` (related-to → Malware)

---

### `text-list-url` — Listas de URLs maliciosas (texto plano)

**Formato de entrada:** Una URL por línea. Las líneas vacías o que comienzan por `#` se ignoran.

**Objetos STIX generados por cada URL:**
- `URL` con el valor de la URL
- `Indicator` con patrón STIX: `[url:value = '<url>']`
- `Relationship` de tipo `based-on` → (Indicator → URL)

---

### `text-list-ip` — Listas de IPs (texto plano)

**Formato de entrada:** Una IP por línea. Las líneas vacías o con `#` se ignoran.

**Filtro aplicado:** Solo se procesan IPs que superen la validación `_is_public_ip()`. IPs privadas, loopback, multicast o de link-local son descartadas.

**Objetos STIX generados por cada IP válida:**
- `IPv4Address` con el valor de la IP

---

## 9. Validación y Seguridad

### Métodos de validación de IP

| Método | Descripción |
|---|---|
| `_is_ip_structure(text)` | Devuelve `True` si el texto puede parsearse como una IP (incluye privadas) |
| `_is_public_ip(ip_str)` | Devuelve `True` solo si la IP es global, no multicast y no privada |

La distinción entre ambos métodos es clave para el parser `drb-json`: primero se comprueba si el campo `C2Server` es una IP (para no crear un `DomainName` con valor `"127.0.0.1"`), y solo después se valida si es pública.

### Método de limpieza de dominio: `_clean_domain(domain)`

Transforma cadenas sucias en dominios válidos:

```
"https://evil.com/path?q=1"  →  "evil.com"
"evil.com:443"               →  "evil.com"
"EVIL.COM"                   →  "evil.com"
"127.0.0.1,8080"             →  "127.0.0.1"  (luego descartada como IP privada)
```

Descartes automáticos:
- Cadenas sin `.`
- Cadenas de longitud < 3
- Valores vacíos o `None`

### Límites de seguridad globales

```python
MAX_FILE_SIZE_MB = 10   # (declarado, no aplicado activamente en v1.2)
TIMEOUT_SECONDS = 30    # Timeout para todas las peticiones HTTP
```

> [!NOTE]
>  la constante `MAX_FILE_SIZE_MB` está declarada como mecanismo de protección frente a feeds anómalamente grandes, pero no se aplica en la versión actual del conector. Durante la fase de pruebas se vio que su integración en el flujo de descarga producía un error de ejecución no resuelto, por lo que se optó por dejarla como constante documental pendiente de implementación. El timeout de 30 segundos en las peticiones HTTP (`TIMEOUT_SECONDS`) actúa de hecho como salvaguarda implícita ante descargas excesivamente lentas o servidores inestables.

---

## 10. Variables de Entorno

| Variable              | Por defecto       | Descripción                                        |
| --------------------- | ----------------- | -------------------------------------------------- |
| `OPENCTI_URL`         | —                 | URL de la instancia OpenCTI (obligatorio)          |
| `OPENCTI_TOKEN`       | —                 | Token de API de OpenCTI (obligatorio)              |
| `CONNECTOR_ID`        | —                 | UUID único del conector (obligatorio)              |
| `CONNECTOR_NAME`      | —                 | Nombre del conector en OpenCTI                     |
| `CONNECTOR_TYPE`      | `EXTERNAL_IMPORT` | Tipo de conector OpenCTI                           |
| `CONNECTOR_RUN_EVERY` | `3600`            | Segundos entre ejecuciones del bucle               |
| `CONNECTOR_LOG_LEVEL` | `info`            | Nivel de log (`debug`, `info`, `warning`, `error`) |

---

## 11. Ciclo de Vida de una Ejecución

```
[Inicio del bucle]
       │
       ▼
Crear trabajo en OpenCTI (work_id)
       │
       ▼
Leer feeds.json
       │
       ├─► [Feed 1] Descargar → Parser drb-json → Bundle STIX → Enviar a OpenCTI
       ├─► [Feed 2] Descargar → Parser drb-json → Bundle STIX → Enviar a OpenCTI
       ├─► [Feed 3] Descargar → Parser text-list-url → Bundle STIX → Enviar a OpenCTI
       └─► [Feed 4] Descargar → Parser text-list-ip → Bundle STIX → Enviar a OpenCTI
       │
       ▼
Marcar trabajo como completado
       │
       ▼
Dormir CONNECTOR_RUN_EVERY segundos
       │
       └─► [Vuelta al inicio]
```

Los errores en un feed individual son capturados y registrados sin interrumpir el procesamiento del resto de feeds.

---

## 12. Objetos STIX2 Generados

Resumen de todos los tipos de objetos STIX que el conector puede producir:

| Objeto STIX | Fuente | Condición |
|---|---|---|
| `Identity` | Todos | Siempre (autor del conector) |
| `Malware` | `drb-json` | Uno por feed procesado |
| `IPv4Address` | `drb-json`, `text-list-ip` | IP pública válida |
| `DomainName` | `drb-json` | C2Server no es IP |
| `URL` | `text-list-url` | Cada línea no vacía/comentada |
| `Indicator` | `text-list-url` | Uno por URL (patrón STIX) |
| `Relationship` | `drb-json`, `text-list-url` | Relaciona IoCs con su padre |

Todos los objetos incluyen:
- `created_by_ref` → referencia al objeto `Identity` del conector
- `labels` → etiquetas definidas en `feeds.json` para ese feed
- `allow_custom=True` → permite campos personalizados de OpenCTI

---

## 13. Añadir una Nueva Fuente

### Paso 1: Editar `feeds.json`

Añade una nueva entrada al array:

```json
{
  "name": "Mi Nuevo Feed",
  "url": "https://mi-fuente.com/iocs.txt",
  "parser": "text-list-ip",
  "interval": 3600,
  "labels": ["malware", "botnet"]
}
```

### Paso 2: (Opcional) Implementar un nuevo parser

Si el formato del feed no encaja con ninguno de los tres parsers existentes, añade un nuevo método en `connector.py`:

```python
def process_mi_formato(self, content: str, labels: List[str]) -> List[Any]:
    objects = [self.author]
    # ... lógica de parseo ...
    return objects
```

Y registra el nuevo parser en el bloque `if/elif` del método `run()`:

```python
elif parser_type == "mi-formato":
    stix_objects = self.process_mi_formato(content, labels)
```

### Paso 3: Reconstruir y reiniciar el contenedor

La forma recomendada de aplicar los cambios es mediante el *script* de administración `opencti-control` (ver anexo correspondiente), que encapsula la operación de reconstruir todas las imágenes de conectores modificadas:

```bash
opencti-control update-connectors
```

---

## 14. Solución de Problemas

### El conector aparece como inactivo en OpenCTI

- Verifica que `CONNECTOR_ID` sea un UUID v4 válido y único.
- Revisa los logs: `docker compose logs -f connector-multifeed`
### No se ingresan objetos de un feed específico

- Verifica en los logs si hay errores de descarga o parseo.
- Asegúrate de que el campo `parser` en `feeds.json` coincide exactamente con uno de los valores admitidos: `drb-json`, `text-list-url`, `text-list-ip`
### Se esperaban dominios pero se ingresan IPs (o viceversa)

- Revisa el contenido raw del feed: puede que el campo `C2Server` contenga IPs en formato de texto.
- La lógica del parser `drb-json` clasifica automáticamente el valor limpio: si `ipaddress.ip_address()` no lanza excepción, se trata como IP.
### Las IPs privadas aparecen en OpenCTI

- Esto no debería ocurrir con el código actual: `_is_public_ip()` filtra todo lo que no sea `is_global`.
- Si ocurre, verifica que el campo procesado pase primero por `_is_ip_structure()` antes de llamar a `_is_public_ip()`.
### Reiniciar el conector sin reconstruir la imagen

```bash
docker compose restart connector-multifeed
```

### Forzar una ejecución inmediata

El conector no dispone de un trigger manual. La forma más directa es reiniciarlo:

```bash
docker compose restart connector-multifeed
```

El bucle comienza inmediatamente al arrancar, antes de que entre en el `sleep`.
