# Documentación: `opencti-control`

**Tipo:** Script de gestión Bash  
**Ubicación:** `/usr/local/bin/opencti-control`  
**Permisos necesarios:** `root` o usuario `opencti_svc`

---

## Descripción General

`opencti-control` es un script de administración que unifica los comandos de Docker Compose para el stack de OpenCTI, evitando tener que navegar manualmente entre directorios y recordar flags de Docker. Gestiona de forma separada e independiente dos capas del sistema:

| Capa | Directorio | Contenido |
|---|---|---|
| **Core** | `/opt/opencti` | Base de datos, backend, frontend |
| **Conectores** | `/opt/opencti/connectors` | Workers, conectores internos y custom |

La salida de los comandos de estado usa colores ANSI para distinguir visualmente el estado de cada contenedor.

---

## Instalación y Configuración

### Ubicar el script en el PATH

```bash
sudo cp opencti-control /usr/local/bin/opencti-control
sudo chmod +x /usr/local/bin/opencti-control
```

Con esto el script queda disponible desde cualquier directorio simplemente como `opencti-control <comando>`.

### Variables de configuración internas

Las rutas y el usuario permitido se definen al inicio del script. Si tu entorno usa rutas distintas, edita estas tres líneas:

```bash
CORE_DIR="/opt/opencti"          # Directorio del Docker Compose del Core
CONN_DIR="/opt/opencti/connectors" # Directorio del Docker Compose de Conectores
ALLOWED_USER="opencti_svc"       # Usuario no-root autorizado a ejecutar el script
```

### Control de acceso

El script solo puede ejecutarse como **`root`** o como el usuario definido en `ALLOWED_USER` (`opencti_svc` por defecto). Cualquier otro usuario recibe un error y el script termina inmediatamente:

```
⛔ ERROR CRÍTICO: Permiso denegado.
```

Para dar permisos de ejecución al usuario `opencti_svc` sin necesidad de `sudo` completo, puedes usar `sudoers`:

```bash
# /etc/sudoers.d/opencti-control
opencti_svc ALL=(ALL) NOPASSWD: /usr/local/bin/opencti-control
```

---

## Referencia de Comandos

### `start` — Iniciar el sistema completo

```bash
opencti-control start
```

Levanta el sistema en orden correcto en tres fases:

```
[1/3] Core (docker compose up -d)
      ↓
[2/3] Espera 15 segundos (inicialización de bases de datos)
      ↓
[3/3] Conectores y Workers (docker compose up -d)
```

> El retardo de 15 segundos es intencional: los conectores dependen de que OpenCTI y sus bases de datos (Elasticsearch, MinIO, Redis, RabbitMQ) estén operativos antes de intentar iniciar.

---

### `stop` — Detener el sistema completo

```bash
opencti-control stop
```

Apaga el sistema en orden inverso al arranque:

```
[1/2] Conectores (docker compose down)
      ↓
[2/2] Core (docker compose down)
```

El orden es importante: bajar el Core antes que los conectores puede provocar errores de desconexión en los workers.

---

### `restart` — Reinicio completo

```bash
opencti-control restart
```

Ejecuta `stop` seguido de `start` con una pausa de 2 segundos entre ambos. Útil para aplicar cambios de configuración que requieren reinicio de todo el stack.

---

### `status` — Estado de los contenedores

```bash
opencti-control status
```

Muestra una tabla con el nombre, estado y status de todos los contenedores de ambos stacks. Los estados se colorean automáticamente:

| Color       | Estado                   |
| ----------- | ------------------------ |
| 🟢 Verde    | `healthy`                |
| 🟢 Verde    | `running`                |
| 🟡 Amarillo | `restarting`, `starting` |
| 🔴 Rojo     | `unhealthy`, `Exited`    |
| 🔵 Azul     | header de la tabla       |

Ejemplo de salida:

```
╔══════════════════════════════════════════════════════════════╗
║             📊  ESTADO DEL SISTEMA OPENCTI                   ║
╚══════════════════════════════════════════════════════════════╝

📂 Core -> /opt/opencti
────────────────────────────────────────────────────────────────
NAME                    STATE     STATUS
opencti-elasticsearch   running   Up 2 hours (healthy)
opencti-minio           running   Up 2 hours (healthy)
opencti-redis           running   Up 2 hours
opencti-rabbitmq        running   Up 2 hours (healthy)
opencti-platform        running   Up 2 hours (healthy)

🔌 CONECTORES (Workers) -> /opt/opencti/connectors
────────────────────────────────────────────────────────────────
NAME                          STATE     STATUS
connector-multifeed           running   Up 1 hour
connector-export-file-stix    running   Up 1 hour
```

---

### `logs-core` — Logs del Core en tiempo real

```bash
opencti-control logs-core
```

Equivale a ejecutar `docker compose logs -f` en `/opt/opencti`. Muestra los logs de todos los servicios del core en tiempo real. Pulsa **Ctrl+C** para salir.

Para filtrar los logs de un servicio concreto del core, usa Docker directamente:

```bash
docker logs -f opencti-platform
```

---

### `logs-connectors` — Logs de conectores en tiempo real

```bash
opencti-control logs-connectors
```

Equivale a `docker compose logs -f` en `/opt/opencti/connectors`. Muestra los logs de todos los conectores y workers. Pulsa **Ctrl+C** para salir.

Para ver solo los logs del conector multifeed por ejemplo:

```bash
docker logs -f connector-multifeed
```

---

### `update-connectors` — Reconstruir y actualizar conectores

```bash
opencti-control update-connectors
```

Equivale a `docker compose up -d --build` en el directorio de conectores. El flag `--build` fuerza a Docker a **reconstruir las imágenes** desde el código fuente antes de levantar los contenedores.

**Cuándo usarlo:**
- Después de modificar `connector.py` del conector multifeed u otro conector custom.
- Después de modificar `feeds.json`.
- Después de añadir o actualizar dependencias en `requirements.txt`.
- Después de cambiar el `Dockerfile` de un conector.
- Después de actualizar el `docker-compose.yml` de los conectores

> Los conectores que no tienen cambios en su imagen **no se reconstruyen** (Docker usa la caché), por lo que el comando es seguro de ejecutar aunque solo hayas cambiado un único conector.

---

## Flujos de Trabajo Habituales

### Despliegue inicial

```bash
opencti-control start
# Esperar ~2 minutos para inicialización completa
opencti-control status
```

### Apagado y encendido programado

```bash
# Apagar
opencti-control stop

# Encender al día siguiente
opencti-control start
```

### Modificar el conector multifeed (o el que sea) y aplicar cambios

```bash
# 1. Editar el código o feeds.json
nano /opt/opencti/custom_connectors/multifeed/feeds.json

# 2. Reconstruir y reiniciar solo los conectores
opencti-control update-connectors

# 3. Verificar que arrancó correctamente
opencti-control status
docker logs -f connector-multifeed
```

### Diagnóstico ante un contenedor en rojo

```bash
# Ver estado general
opencti-control status

# Obtener los últimos logs del contenedor problemático
docker logs --tail 100 <nombre-del-contenedor>

# Reiniciar solo ese contenedor sin tocar el resto
docker restart <nombre-del-contenedor>
```

### Reinicio completo por cambio de configuración del Core

```bash
opencti-control restart
```

---

## Mensajes de Error

| Mensaje | Causa | Solución |
|---|---|---|
| `⛔ ERROR CRÍTICO: Permiso denegado.` | El usuario actual no es `root` ni `opencti_svc` | Ejecutar como usuario correcto o con `sudo` |
| `⛔ Error: No se encuentran los directorios.` | `CORE_DIR` o `CONN_DIR` no existen | Verificar rutas en las variables de configuración del script |
| `Uso: opencti-control {start\|stop\|...}` | Comando no reconocido | Revisar la lista de comandos válidos |

---

## Info rápida

```
opencti-control start               → Arranca Core y luego Conectores
opencti-control stop                → Para Conectores y luego Core
opencti-control restart             → stop + start
opencti-control status              → Tabla de estado con colores
opencti-control logs-core           → Logs en vivo del Core (Ctrl+C para salir)
opencti-control logs-connectors     → Logs en vivo de Conectores (Ctrl+C para salir)
opencti-control update-connectors   → Reconstruye imágenes y reinicia Conectores
```
