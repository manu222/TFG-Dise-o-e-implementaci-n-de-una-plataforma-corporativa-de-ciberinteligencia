
# 1. Requisitos de la Máquina Virtual

![Proxmox Config](../imgs-wazuh/wazuh-proxmox.png)

# Manual Técnico: Despliegue de Wazuh SIEM/XDR

# Propósito y contexto

Este anexo documenta el despliegue de Wazuh como solución SIEM/XDR (*Security Information and Event Management* / *Extended Detection and Response*) sobre el laboratorio CTI. Su rol arquitectónico se describe a alto nivel en el apartado 3.2.3 (Detección y Telemetría) de la memoria, y su validación funcional en el apartado 3.6.2 (Plan de pruebas y casos de uso validados).

## Decisión de despliegue: instalación nativa frente a contenerizada

La planificación inicial contemplaba desplegar Wazuh contenerizado mediante Docker, en coherencia con el resto del *stack*. Durante la fase de implementación se evidenció la inviabilidad de este modelo por conflictos en la gestión de la PKI interna de Wazuh (los certificados TLS que cifran la comunicación bidireccional entre agentes y manager) y los volúmenes persistentes de Docker. Esta desviación está documentada en el apartado 3.2.3.A de la memoria, y motivó la migración a la **instalación nativa *all-in-one*** que se documenta en este anexo.

## Tabla de variables del despliegue

| **Variable**      | **Valor / Descripción**                                                 |
| :---------------- | :---------------------------------------------------------------------- |
| **Plataforma**    | Proxmox VE                                                              |
| **S.O. Guest**    | Debian 13                                                               |
| **Modelo**        | All-In-One (indexer + manager + dashboard en la misma VM)               |
| **Red LAN**       | 10.0.0.0/24 (Laboratorio CTI)                                           |
| **Hostname FQDN** | `wazuh.ryoiki` (resolución vía Unbound DNS de OPNsense)                 |
| **Agentes**       | Desplegados en las VMs del laboratorio que requieren monitorización     |
| **Integración**   | Webhook hacia n8n para disparar el flujo SOAR (ver anexo Workflow SOAR) |

---

| **Componente**     | **Especificación Mínima** | **Asignación en Proxmox** |
| ------------------ | ------------------------- | ------------------------- |
| **CPU**            | 4 vCores                  | **4 vCores**              |
| **Memoria RAM**    | 8 GB                      | **8 GB**                  |
| **Almacenamiento** | 50 GB                     | **80 GB**                 |
| **Red**            | 1 Interfaz                | `vmbr1` (Bridge)          |

## 2. Preparación del Sistema Base

```Bash
# 1. Actualización de repositorios y del sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalación de utilidades esenciales
sudo apt install -y curl apt-transport-https unzip wget libcap2-bin software-properties-common lsb-release gnupg2
```

## 2.1 Registro DNS previo en OPNsense

Para que el agente pueda resolver el FQDN `wazuh.ryoiki` que se utilizará durante la instalación y registro de los agentes, debe crearse previamente el correspondiente *host override* en el servicio Unbound DNS de OPNsense, de forma análoga al que ya existe para OpenCTI.

- [x] Acceder a OPNsense → **Services > Unbound DNS > Overrides > Host Overrides**.
- [x] Clic en `+` para añadir.

| Parámetro       | Valor de Configuración                    |
| :-------------- | :---------------------------------------- |
| **Host**        | `wazuh`                                   |
| **Domain**      | `ryoiki`                                  |
| **IP**          | `10.0.0.X` *(IP real de la VM Wazuh)*     |

- [x] Guardar y aplicar cambios.

Este registro permite que cualquier agente desplegado en una VM del laboratorio resuelva `wazuh.ryoiki` y se comunique con el manager por nombre en lugar de por IP. Si en el futuro la VM Wazuh cambia de IP, basta con actualizar el registro en OPNsense sin tocar la configuración de los agentes ya desplegados.

---
## 3. Instalación Nativa mediante _Wazuh Installation Assistant_

Wazuh proporciona un script oficial que orquesta la instalación de los paquetes `.deb`, la configuración de repositorios y la generación de certificados TLS para la comunicación interna entre los nodos.

### 3.1. Descarga y Ejecución del Asistente

Ejecutaremos el script con el parámetro `-a` (All-in-One) que automatiza todo el flujo.

```Bash
# Descargar el script de instalación
curl -sO https://packages.wazuh.com/4.14/wazuh-install.sh

# Ejecutar el asistente en modo desatendido (All-In-One)
sudo bash ./wazuh-install.sh -a
```

### 3.2. Captura de Credenciales

Al finalizar la instalación, el script generará unas contraseñas aleatorias para los usuarios administradores. **Es vital copiarlas**. El sistema mostrará algo similar a esto por pantalla:

> [!IMPORTANT] estas credenciales se muestran una única vez al final de la instalación. Si se pierden, pueden regenerarse mediante el script oficial:

 ```bash
 sudo /usr/share/wazuh-indexer/plugins/opensearch-security/tools/wazuh-passwords-tool.sh -au admin -ac <nueva_password>
 ```

```Plaintext
INFO: --- Summary ---
INFO: You can access the web interface https://<wazuh-dashboard-ip>
    User: admin
    Password: <ADMIN_PASSWORD>
INFO: Installation finished.
```

## 4. Gestión de Servicios y Verificación (`systemd`)

Como la instalación es nativa, no usamos contenedores. Todos los servicios son gestionados por `systemctl`. A continuación, se detallan los comandos para verificar que el stack de servicios de Wazuh funciona correctamente:

|Servicio|Descripción|Comando de Estado|
|---|---|---|
|`wazuh-indexer`|Base de datos analítica|`sudo systemctl status wazuh-indexer`|
|`wazuh-manager`|Motor de recolección y reglas|`sudo systemctl status wazuh-manager`|
|`wazuh-dashboard`|Interfaz gráfica (Web GUI)|`sudo systemctl status wazuh-dashboard`|

**Comprobación del estado de los puertos clave:** Para asegurar que los servicios están escuchando, podemos utilizar `ss` o `netstat`:

```Bash
# Comprobar escucha de agentes (1514) y API (55000)
sudo ss -tulpn | grep -E "1514|55000|443|9200"
```

## 5. Instalación de agentes Wazuh

Sustituir las variables `WAZUH_MANAGER`, `WAZUH_AGENT_GROUP` y `WAZUH_AGENT_NAME` según el host donde se instale el agente. El comando descarga el `paquete.deb` del agente y lo instala con las variables ya inyectadas en una sola operación:`

```bash
wget https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.14.4-1_amd64.deb && sudo WAZUH_MANAGER='wazuh.ryoiki' WAZUH_AGENT_GROUP='default' WAZUH_AGENT_NAME='Test' dpkg -i ./wazuh-agent_4.14.4-1_amd64.deb
```

---

## 6. Configuración de File Integrity Monitoring (FIM)

El caso de uso 2 del plan de pruebas (apartado 3.6.2 de la memoria) requiere monitorizar la integridad de ficheros sensibles para detectar modificaciones no autorizadas (en el escenario validado, una *webshell* PHP). Esta capacidad se configura mediante el módulo *syscheck* del agente Wazuh.
### Activación de FIM en el agente

Editar el fichero de configuración del agente:

```bash
sudo nano /var/ossec/etc/ossec.conf
```

Localizar el bloque `<syscheck>` y añadir las rutas a monitorizar dentro del segmento `<directories>`. Para el caso del servidor web monitorizado:

```xml
<syscheck>
  <disabled>no</disabled>
  <frequency>43200</frequency>  <!-- Verificación periódica cada 12 horas -->

  <!-- Monitorización de cambios en tiempo real sobre el directorio web -->
  <directories check_all="yes" realtime="yes" report_changes="yes">/var/www/html</directories>

  <!-- Otros ejemplos de directorios sensibles -->
  <directories check_all="yes" realtime="yes">/etc</directories>
  <directories check_all="yes">/usr/bin,/usr/sbin</directories>
</syscheck>
```

Atributos relevantes:

- **`realtime="yes"`** — usa `inotify` del kernel para detectar cambios en el momento en que se producen, sin esperar al siguiente ciclo periódico. Es el modo necesario para detectar la creación de una *webshell* en el instante.
- **`report_changes="yes"`** — incluye en la alerta un *diff* del contenido modificado, no solo la notificación de cambio.
- **`check_all="yes"`** — verifica todos los atributos del fichero (tamaño, permisos, MD5, SHA1, SHA256, propietario, grupo).

Tras editar la configuración, reiniciar el agente:

```bash
sudo systemctl restart wazuh-agent
```

### Verificación

Modificar manualmente un fichero dentro del directorio monitorizado y comprobar que la alerta aparece en el dashboard de Wazuh (`https://wazuh.ryoiki` → **Threat Hunting > Events**), o consultando los logs en el manager:

```bash
sudo tail -f /var/ossec/logs/alerts/alerts.log | grep "syscheck"
```

---

## 7. Integración con el orquestador SOAR (n8n)

La detección de eventos por sí sola es insuficiente para un modelo proactivo. Para que las alertas críticas disparen el flujo SOAR descrito en el apartado 3.2.5 de la memoria, se configura el módulo `<integration>` del manager Wazuh para que envíe las alertas vía webhook a n8n.
### Configuración en el manager

Editar el fichero de configuración del manager:

```bash
sudo nano /var/ossec/etc/ossec.conf
```

Añadir dentro del bloque `<ossec_config>` la siguiente integración:

```xml
<integration>
  <name>custom-n8n</name>
  <hook_url>http://n8n.ryoiki:5678/webhook/webhook-test/wazuh-poc2</hook_url>
  <level>1</level>
  <alert_format>json</alert_format>
</integration>
```

Parámetros:

- **`name`** — debe coincidir con el nombre de un script en `/var/ossec/integrations/` o usar `custom-` como prefijo para indicar al manager que envíe directamente la alerta como POST JSON sin script intermedio.
- **`hook_url`** — URL del webhook generado por el nodo *Webhook* del flujo SOAR en n8n (la URL exacta se obtiene del propio workflow una vez activado).
- **`level`** — nivel mínimo de alerta que dispara la integración. Wazuh clasifica las reglas con niveles del 0 al 15
- **`alert_format`** — `json` envía el payload completo de la alerta en formato JSON, que es el que el flujo SOAR espera y procesa con consultas GraphQL hacia OpenCTI.

Reiniciar el manager para aplicar:

```bash
sudo systemctl restart wazuh-manager
```

### Verificación

Generar manualmente una alerta de nivel ≥ 10 (por ejemplo, simulando un ataque de fuerza bruta SSH como en el caso 1 del plan de pruebas) y comprobar en n8n que el webhook ha recibido el evento. La descripción detallada del flujo posterior se encuentra en el anexo **Workflow SOAR**.

---