# Documentación Técnica: Conector OpenCTI Gemini Enrichment

**Proyecto:** TFG Ciberseguridad  
**Tipo:** Conector de Enriquecimiento Interno (`INTERNAL_ENRICHMENT`)  
**Versión:** 1.0  
**IA utilizada:** Google Gemini (API Google AI for Developers)

---

> ⚠️ **LIMITACIÓN IMPORTANTE — API de Desarrollador de Google**
>
> Este conector fue desarrollado usando la capa gratuita de la **Google AI for Developers API**. Dicha capa tiene una cuota de peticiones extremadamente reducida que, en las pruebas realizadas, **se agotó tras el primer uso completo del conector**.
>
> A pesar de esta limitación, el conector **logra ejecutarse satisfactoriamente**: recibió el objeto de OpenCTI, envio la informacion a la API de gemini, pero esta consumia todos los tokens inmediatamente antes de poder responder, se llega a la conclusion de que con una API extendida en un entorno empresarial, no nos topariamos con este inconveniente. Para un entorno real se deberia usar una API para un modelo de IA con conexion a internet para contar con la información mas actualizada, por eso no se usa un modelo de IA local en este campo

---

## Tabla de Contenidos

1. [Descripción General](#1-descripción-general)
2. [Arquitectura y Estructura de Archivos](#2-arquitectura-y-estructura-de-archivos)
3. [Dependencias](#3-dependencias)
4. [Imagen Docker](#4-imagen-docker)
5. [Integración en el Docker Compose](#5-integración-en-el-docker-compose)
6. [Variables de Entorno](#6-variables-de-entorno)
7. [Lógica del Conector (`gemini_connector.py`)](#7-lógica-del-conector-gemini_connectorpy)
8. [El Prompt de Análisis](#8-el-prompt-de-análisis)
9. [Resultado: La Nota en OpenCTI](#9-resultado-la-nota-en-opencti)
10. [Cómo Usar el Conector desde OpenCTI](#10-cómo-usar-el-conector-desde-opencti)
11. [Limitaciones Conocidas](#11-limitaciones-conocidas)
12. [Solución de Problemas](#12-solución-de-problemas)

---

## 1. Descripción General

El conector **Gemini Enrichment** es un conector de tipo enriquecimiento para OpenCTI que, al ser invocado manualmente sobre cualquier entidad STIX (malware, actor de amenaza, indicador, etc.), envía toda la información disponible de esa entidad a la API de **Google Gemini** y solicita un análisis técnico en español. El resultado se guardara automáticamente como una **Nota** vinculada al objeto analizado dentro de OpenCTI.

A diferencia del conector Multi-Feed, este conector **no opera en bucle periódico**: se activa bajo demanda, evento a evento, cuando el analista pulsa el botón de enriquecimiento desde la interfaz de OpenCTI.

### Flujo resumido

```
Analista pulsa "Enriquecer" en OpenCTI
         ↓
Conector recibe el ID del objeto
         ↓
Consulta la API de OpenCTI para obtener todos los datos del objeto
         ↓
Construye un prompt en español con esos datos
         ↓
Envía el prompt a Google Gemini
         ↓
Recibe el análisis en Markdown
         ↓
Guarda el análisis como Nota vinculada al objeto en OpenCTI
```

---

## 2. Arquitectura y Estructura de Archivos

```
/opt/opencti/custom_connectors/gemini_enrichment/
├── gemini_connector.py    # Lógica principal del conector
├── requirements.txt       # Dependencias Python
└── Dockerfile             # Imagen Docker del conector
```

---

## 3. Dependencias

Definidas en `requirements.txt`:

| Paquete | Versión | Función |
|---|---|---|
| `pycti` | `6.4.1` | SDK oficial de OpenCTI para conectores |
| `stix2` | `3.0.1` | Manipulación de objetos STIX 2.1 |
| `google-generativeai` | `0.8.3` | Cliente Python oficial de Google Gemini |
| `markdown` | `3.7` | Procesamiento de la respuesta Markdown de Gemini |

---

## 4. Imagen Docker

```
Base:      python:3.12-slim
WorkDir:   /opt/opencti-connector-gemini
Usuario:   opencti (no-root)
EntryPoint: python3 gemini_connector.py
```

### Diferencias respecto al Dockerfile del Multi-Feed

El Dockerfile de este conector es más ligero: no incluye `build-essential` ni `git` ya que no requiere compilación de extensiones nativas. Solo instala `curl`, `ca-certificates` y `libmagic1` como dependencias del sistema.

### Construir la imagen manualmente

```bash
cd /opt/opencti/custom_connectors/gemini
docker build -t opencti-connector-gemini:latest .
```

---

## 5. Integración en el Docker Compose

Bloque de servicio para el `docker-compose.yml` de `/opt/opencti/connectors`:

```yaml
  connector-gemini:
    build: ../custom_connectors/gemini_enrichment
    image: opencti/connector-gemini:latest
    environment:
      - OPENCTI_URL=http://opencti:8080
      - OPENCTI_TOKEN=${GEMINI_USER_TOKEN}
      - CONNECTOR_ID=${CONNECTOR_GEMINI_TOKEN}
      - CONNECTOR_TYPE=INTERNAL_ENRICHMENT
      - CONNECTOR_NAME=Gemini AI Analyst
      - CONNECTOR_SCOPE=Malware,Indicator,Report,Attack-Pattern,Intrusion-Set,Tool
      - CONNECTOR_AUTO=false
      - CONNECTOR_CONFIDENCE_LEVEL=80
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GEMINI_MODEL=gemini-3-pro-preview
      - GEMINI_TEMPERATURE=0.2
      - GEMINI_MAX_TOKENS=2048
    restart: always
    networks:
      - opencti_net
```

> `CONNECTOR_SCOPE` define sobre qué tipos de entidades de OpenCTI aparecerá el botón de enriquecimiento de Gemini. Se pueden añadir más tipos separados por coma.

---

## 6. Variables de Entorno

### Variables de OpenCTI (comunes a todos los conectores)

| Variable | Descripción |
|---|---|
| `OPENCTI_URL` | URL de la instancia OpenCTI |
| `OPENCTI_TOKEN` | Token de API de OpenCTI |
| `CONNECTOR_ID` | UUID v4 único del conector |
| `CONNECTOR_NAME` | Nombre visible en OpenCTI |
| `CONNECTOR_TYPE` | `INTERNAL_ENRICHMENT` |
| `CONNECTOR_SCOPE` | Tipos de entidad que el conector puede procesar |
| `CONNECTOR_LOG_LEVEL` | Nivel de log (`debug`, `info`, `warning`, `error`) |

### Variables propias del conector Gemini

| Variable             | Por defecto            | Descripción                                                      |
| -------------------- | ---------------------- | ---------------------------------------------------------------- |
| `GEMINI_API_KEY`     | —                      | Clave de la API de Google AI (**obligatoria**)                   |
| `GEMINI_MODEL`       | `gemini-3-pro-preview` | Nombre del modelo Gemini a usar                                  |
| `GEMINI_TEMPERATURE` | `0.2`                  | Creatividad de la respuesta (0.0 = determinista, 1.0 = creativo) |
| `GEMINI_MAX_TOKENS`  | `2048`                 | Longitud máxima de la respuesta generada                         |

> **Sobre `GEMINI_TEMPERATURE`:** Un valor bajo (0.2) favorece respuestas más precisas y técnicas, adecuadas para análisis de seguridad. Valores altos producen respuestas más variadas y creativas, menos apropiadas para este caso de uso.

---

## 7. Lógica del Conector (`gemini_connector.py`)

### Clase principal: `GeminiEnrichmentConnector`

#### `__init__()` — Inicialización

En el arranque el conector:

1. Instancia el `OpenCTIConnectorHelper` para comunicarse con OpenCTI.
2. Lee las variables de entorno de Gemini (`API_KEY`, `MODEL`, `TEMPERATURE`, `MAX_TOKENS`).
3. Valida que `GEMINI_API_KEY` esté presente; si no, lanza un `ValueError` y el contenedor no arranca.
4. Configura el cliente de Google Generative AI con el modelo y parámetros indicados.

#### `_process_message(data)` — Manejador de eventos

Se activa cada vez que OpenCTI envía un evento de enriquecimiento al conector. Recibe un dict con el campo `entity_id`.

```
1. Lee el objeto completo desde la API de OpenCTI (entity_id → entidad STIX)
2. Llama a _generate_analysis() con los datos del objeto
3. Guarda el resultado como Nota en OpenCTI vinculada al objeto
```

#### `_generate_analysis(entity_type, entity_name, description, stix_objects)` — Llamada a Gemini

Construye el prompt con los datos del objeto y lo envía a Google Gemini. Devuelve el texto Markdown de la respuesta, o un mensaje de error si la llamada falla.

#### `start()` — Bucle de escucha

Llama a `self.helper.listen(self._process_message)`, que mantiene el conector a la espera de eventos de OpenCTI indefinidamente. A diferencia del Multi-Feed, **no tiene `sleep`**: reacciona a eventos en tiempo real.

---

## 8. El Prompt de Análisis

El conector instruye a Gemini para actuar como analista de ciberseguridad y generar un informe estructurado en español con tres secciones fijas:

### Sección 1 — Resumen
Descripción del riesgo, nivel de peligrosidad y familia de malware o actor si se conoce.

### Sección 2 — Análisis Técnico
TTPs (Tácticas, Técnicas y Procedimientos), capacidades, indicadores relacionados y comportamiento observado en los datos STIX proporcionados.

### Sección 3 — Recomendaciones de Mitigación
Pasos concretos para defender o remediar la amenaza analizada.

### Parámetros del prompt

| Parámetro | Valor |
|---|---|
| Idioma de salida | Español |
| Formato de salida | Markdown con cabeceras `###` |
| Instrucción anti-alucinación | El modelo debe indicar explícitamente si falta información, en vez de inventarla |
| Temperature | 0.2 (respuestas técnicas y precisas) |

---

## 9. Resultado: La Nota en OpenCTI

Tras el análisis, el conector crea un objeto `Note` en OpenCTI con:

| Campo | Valor |
|---|---|
| `abstract` | `Análisis IA (Gemini): <nombre del objeto>` |
| `content` | Informe completo en Markdown generado por Gemini |
| `created_by_ref` | El mismo autor del objeto analizado |
| `object_marking_refs` | Los mismos marcadores TLP del objeto analizado |
| `object_refs` | Referencia al objeto analizado (la nota aparece vinculada) |

La nota queda accesible desde la pestaña **"Notas"** del objeto en OpenCTI y es visible para todos los usuarios con acceso a ese objeto.

Se adjunta la imagen de lo comentado anteriormente:
![Nota quota error](../../../imgs-openctiDOC/gemini_enrichment.png)


---

## 10. Cómo Usar el Conector desde OpenCTI

1. Navegar a cualquier entidad que esté dentro del `CONNECTOR_SCOPE` (Malware, Actor de Amenaza, etc.).
2. En el panel lateral derecho o en el menú de acciones, localizar el botón del conector **GeminiEnrichment**.
3. Pulsar el botón para lanzar el enriquecimiento.
4. Esperar unos segundos mientras Gemini procesa la petición.
5. Ir a la pestaña **Notas** del objeto: aparecerá el informe de análisis en Markdown.

---

## 11. Limitaciones Conocidas

| Limitación                              | Detalle                                                                                                                                                                                                    |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cuota de API agotada**                | La API gratuita de Google AI for Developers tiene cuotas mínimas. En las pruebas del TFG se agotó tras el primer uso. Ver nota al inicio del documento.                                                    |
| **Sin procesamiento por lotes**         | El conector procesa un objeto a la vez. No está diseñado para enriquecer múltiples entidades en paralelo.                                                                                                  |
| **Dependencia de conectividad externa** | El contenedor necesita acceso a internet para alcanzar `generativelanguage.googleapis.com`.                                                                                                                |
| **Calidad del análisis**                | La calidad depende de los datos disponibles en OpenCTI. Objetos con poca información recibirán análisis genéricos.                                                                                         |
| **Modelo hardcodeado como fallback**    | El valor por defecto de `GEMINI_MODEL` en el código es `gemini-3-pro-preview` (nombre de prueba); se recomienda establecer siempre la variable en el Compose con el nombre correcto del modelo disponible. |

---

## 12. Solución de Problemas

### El contenedor arranca pero no aparece el botón en OpenCTI

- Verifica que `CONNECTOR_SCOPE` incluye el tipo de entidad sobre la que estás probando.
- Comprueba que el conector está registrado en OpenCTI: en el menú de administración → Conectores.
- Revisa los logs: `docker logs -f connector-gemini-enrichment`.

### El botón aparece pero el análisis no genera ninguna nota

- Revisa los logs del conector buscando mensajes de error de Gemini.
- Comprueba que `GEMINI_API_KEY` es válida y tiene cuota disponible.
- Verifica la conectividad del contenedor hacia Google: `docker exec connector-gemini-enrichment curl -I https://generativelanguage.googleapis.com`.

### Error `GEMINI_API_KEY` al arrancar

- La variable no está definida en el entorno Docker. Asegúrate de que el fichero `.env` del directorio de conectores contiene `GEMINI_API_KEY=<tu_clave>` y que el Compose la referencia con `${GEMINI_API_KEY}`.

### Reconstruir el conector tras cambios en el código

```bash
opencti-control update-connectors
# o directamente:
cd /opt/opencti/connectors
docker compose up -d --build connector-gemini-enrichment
```
