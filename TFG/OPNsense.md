
# Manual Técnico: Despliegue de OPNsense y VPN WireGuard
| **Variable**       | **Valor / Descripción**                                                        |
| :----------------- | :----------------------------------------------------------------------------- |
| **Plataforma**     | Proxmox VE                                                                     |
| **S.O. Guest**     | OPNsense (basado en FreeBSD)                                                   |
| **Servicio VPN**   | WireGuard                                                                      |
| **Red LAN**        | 10.0.0.0/24 (Laboratorio CTI)                                                  |
| Túnel address WG** | 10.10.10.1/24                                                                  |
| **Objetivo**       | Proveer acceso remoto cifrado y seguro a la red ademas de actuar como firewall |
```table-of-contents

```

---

# Tabla de Contenidos

1. [Requisitos y Preparación de la VM](#1-requisitos)
2. [Instalación Base de OPNsense](#2-instalacion-base)
3. [Configuración Inicial de Red](#3-configuracion-red)
4. [Instalación y Configuración de WireGuard](#4-configuracion-wireguard)
    - [4.1 Habilitar el Servicio](#41-habilitar-servicio)
    - [4.2 Configurar la Instancia Local (Servidor)](#42-instancia-local)
    - [4.3 Configurar los Peers (Clientes)](#43-configurar-peers)
5. [Reglas de Firewall y NAT](#5-reglas-firewall)
6. [Configuración del Cliente (Ejemplo)](#6-configuracion-cliente)
7. [DNS-Override](#7-DNS-Override)
8.  [Arquitectura](#8-diagrama-arquitectura)
```toc
title: 
style: nestedList # TOC style (nestedList|nestedOrderedList|inlineFirstLevel)
minLevel: 0 # Include headings from the specified level
maxLevel: 0 # Include headings up to the specified level
include: 
exclude: 
includeLinks: true # Make headings clickable
hideWhenEmpty: false # Hide TOC if no headings are found
debugInConsole: false # Print debug info in Obsidian console
```
---

## 1. Requisitos y Preparación de la VM <a id="1-requisitos"></a>
 **Dimensionamiento del Firewall**

OPNsense actuará como el router perimetral y servidor VPN de la infraestructura.

| Recurso        | Recomendado (Laboratorio) | Notas Proxmox                                                                    |
| :------------- | :------------------------ | :------------------------------------------------------------------------------- |
| **vCPU**       | 2 Cores                   | Tipo de CPU: `host` para mejor cifrado (AES-NI).                                 |
| **RAM**        | 2 GiB                     | Suficiente para enrutamiento y WireGuard.                                        |
| **Disco**      | 25 GB                     | Tipo de bus: `VirtIO Block`.                                                     |
| **Red (NICs)** | 2 Interfaces              | `net0` (WAN/Bridge Externo), `net1` (LAN/Bridge Interno). Modelo: `intel E1000`. |


![Proxmox Config](../imgs-OPNsense/proxmox_opnsense.png)

- [x] Descargar la imagen ISO de OPNsense (arquitectura amd64, versión `dvd`).
- [x] Crear VM en Proxmox adjuntando las dos interfaces de red.

---

## 2. Instalación Base de OPNsense <a id="2-instalacion-base"></a>
 **Proceso de instalación del SO**

1. Arrancar la VM con la ISO montada.
2. Esperar al prompt de login (Live CD).
3. **Credenciales por defecto:**
   - Usuario: `installer`
   - Contraseña: `opnsense`

1. Seguir el asistente gráfico (bsdinstall):
   - [x] Seleccionar mapa de teclado (Spanish/ES).
   - [x] **Install (UFS/ZFS):** Para VMs, ZFS es ideal si Proxmox no gestiona el almacenamiento, de lo contrario UFS (Auto) es más ligero.
   - [x] Finalizar instalación, desmontar la ISO y reiniciar.

---

## 3. Configuración Inicial de Red <a id="3-configuracion-red"></a>
 **Asignación de Interfaces vía CLI**

Tras reiniciar, inicia sesión con `root` y contraseña `opnsense`. Aparecerá el menú de consola.

- [x] Seleccionar la opción `1) Assign interfaces`.
- [x] ¿Configurar LAGGs? `No`.
- [x] ¿Configurar VLANs? `No`.
- [x] Asignar **WAN**: Seleccionar la interfaz correspondiente (ej. `em0`).
- [x] Asignar **LAN**: Seleccionar la interfaz correspondiente (ej. `em1`).
- [x] Presionar `y` para aplicar.
- [x] Seleccionar la opción `2) Set interface IP address` para configurar la LAN (Ej: `10.0.0.1/24`).

> **Nota para el TFG:** A partir de este momento, la configuración se realiza desde el navegador web accediendo a `https://10.0.0.1` desde una máquina en la red LAN., se recomienda crear una con una distro ultra ligera como lubuntu

---

## 4. Instalación y Configuración de WireGuard <a id="4-configuracion-wireguard"></a>

### 4.1 Habilitar el Servicio <a id="41-habilitar-servicio"></a>
En versiones recientes de OPNsense, el plugin puede venir instalado. Si no:
- [x] Ir a **System > Firmware > Plugins**.
- [x] Buscar e instalar `os-wireguard`.
- [x] Ir a **VPN > WireGuard > Settings** y marcar `Enable WireGuard`.


**Fundamento Criptográfico (Cryptokey Routing)** A diferencia de otras VPNs que usan certificados complejos, WireGuard se basa en un concepto muy simple inspirado en SSH: **el intercambio de claves asimétricas (Curva Elíptica 25519)**.
Para que un túnel se levante, la confianza debe ser mutua y estar preconfigurada: 
1. **El Servidor (OPNsense) necesita conocer al Cliente:** Para autorizar la conexión de un dispositivo, debemos crear un "Peer" en OPNsense e introducir explícitamente la **clave pública del cliente**. Si la clave no está registrada, el firewall descartará los paquetes silenciosamente. 
2. **El Cliente necesita conocer al Servidor:** El archivo de configuración del cliente debe contener la **clave pública del servidor OPNsense** para saber que se está conectando al endpoint legítimo y poder cifrar el tráfico de ida. Por tanto, el paso crítico de la configuración consiste en intercambiar y registrar las claves públicas de ambos extremos.

### 4.2 Configurar la Instancia Local (Servidor) <a id="42-instancia-local"></a>
- [x] Ir a **VPN > WireGuard > Local**.
- [x] Clic en el botón `+` para añadir.

| Parámetro                | Valor de Configuración                              |
| :----------------------- | :-------------------------------------------------- |
| **Name**                 | `VPN_nexus`                                         |
| **Public / Private Key** | *Hacer clic en el icono del engranaje para generar* |
| **Listen Port**          | `51820` (Puerto por defecto)                        |
| **Tunnel Address**       | `10.10.10.1/24` (Rango exclusivo para la VPN)       |
| **Peers**                | *Dejar en blanco por ahora*                         |

- [x] Guardar y aplicar cambios (`Apply`).

### 4.3 Configurar los Peers (Clientes) <a id="43-configurar-peers"></a>
- [x] Ir a **VPN > WireGuard > Endpoints** (o Peers).
- [x] Clic en el botón `+`.

| Parámetro       | Valor de Configuración                                        |
| :-------------- | :------------------------------------------------------------ |
| **Name**        | `Cliente_Admin_1`(Para identificar el equipo)                 |
| **Public Key**  | *[Pegar aquí la clave pública generada en el PC del cliente]* |
| **Allowed IPs** | `10.10.10.2/32` (IP estática asignada a este cliente)         |

- [x] Volver a **VPN > WireGuard > Local**, editar `WG_Server` y añadir este peer en el campo **Peers**.
- [x] Guardar y aplicar.

---

## 5. Reglas de Firewall y NAT <a id="5-reglas-firewall"></a>
**Permitir el tráfico de la VPN**

Para que el túnel funcione, hay que abrir puertos y permitir enrutamiento.

**Paso 1: Abrir el puerto en la WAN**
- [x] Ir a **Firewall > Rules > WAN**.
- [x] Crear nueva regla:
  - **Action:** Pass
  - **Interface:** WAN
  - **Direction:** IN
  - **Protocol:** UDP
  - **Destination:** any
  - **Destination port range:** `51820` to `51820`
  - **Description:** `Allow WireGuard Inbound`(O la que quieras que permita identificar para que es)
  ![Regla udp wireguard](../imgs-OPNsense/regla-udp.png)

**Paso 2: Permitir tráfico interno del túnel WG por shh para acceder a las maquinas**
- [x] Ir a **Firewall > Rules > WireGuard** (Esta pestaña aparece automáticamente).
- [x] Crear nueva regla:
  - **Action:** Pass
  - **Protocol:** TCP
  - **Source:** any
  - **Destination:** This Firewall, WAN net, WAN address, LAN net
  - **Destination port range:** `ssh` to `ssh`
  - **Description:** `Allow all traffic from WireGuard clients to ssh`

---

## 6. Configuración del Cliente (Ejemplo Windows/Linux) <a id="6-configuracion-cliente"></a>
 **Archivo `wg0.conf` para el cliente**

En la máquina remota del administrador (tu PC local), crea este archivo de configuración en el cliente de WireGuard (Tienes que tener instalado wireguard):

```ini
[Interface]
# Clave privada generada en el PC del cliente
PrivateKey = <CLAVE_PRIVADA_DEL_CLIENTE>
Address = 10.10.10.2/32
DNS = 10.0.0.1  # IP LAN de OPNsense

[Peer]
# Clave pública copiada desde la instancia creada anteriormente
PublicKey = <CLAVE_PUBLICA_DEL_SERVIDOR_OPNSENSE>
# IP Pública de tu router / OPNsense
Endpoint = IP_PUBLICA_O_DDNS:51820
# Redes a las que se puede acceder por la VPN (10.0.0.0/24 es el lab)
AllowedIPs = 10.0.0.0/24, 10.10.10.0/24
PersistentKeepalive = 25
```

## 7. DNS Override  <a id="7-DNS-Override"></a>

> [!WARNING] > **Aviso sobre TLDs: El problema del dominio `.nexus`** > > Durante la fase de diseño, se debe evitar el uso de dominios como `.nexus` (ej. `opencti.nexus`) para entornos de laboratorio locales. El dominio `.nexus` es un dominio oficial de Internet (gTLD) que está incluido en la lista de precarga **HSTS (HTTP Strict Transport Security)**. > > Esta directiva obliga a los navegadores web modernos a requerir exclusivamente conexiones seguras mediante certificados HTTPS válidos y emitidos por entidades certificadoras públicas. Como consecuencia, cualquier intento de acceder a un servicio local configurado con HTTP estándar (o con certificados autofirmados que no coincidan) será **bloqueado automáticamente e irrevocablemente por el navegador**. > > **Solución:** Utilizar dominios reservados para uso privado según el RFC 6762/RFC 8375, como `.lab`, `.local` o `.home.arpa`. Tambien puedes inventar uno como se ve a continuación

**Configuración en OPNsense:** 
- [x] Ir a **Services > Unbound DNS > Overrides**.
- [x] En la pestaña **Host Overrides**, hacer clic en `+`. 
- [x] Configurar los siguientes campos: 
- **Host:** `opencti` (El nombre de la máquina). 
- **Domain:** `ryoiki` (El dominio local seguro elegido). 
- **IP:** `10.0.0.2` (La IP real del servidor OpenCTI en la LAN). 
- **Description:** `Algo indentificativo`. 
- [x] Guardar y aplicar cambios. *(Ahora la URL de acceso será `http://opencti.ryoiki:8080` o `https://opencti.ryoiki`)*.

![Override](../imgs-opnsense/dns-override.png)

## 8. Arquitectura  <a id="8-diagrama-arquitectura"></a>

```mermaid
graph LR
    subgraph "Cliente Remoto"
        PC[PC Admin<br>Cliente WG<br>DNS: 10.0.0.1]
    end
    
    subgraph "OPNsense Firewall"
        WG[WireGuard<br>10.10.10.1]
        DNS[Unbound DNS<br>opencti.ryoiki -> 10.0.0.2]
        FW{Firewall/NAT}
    end
    
    subgraph "Laboratorio CTI"
        OCTI[VM OpenCTI<br>10.0.0.2]
    end
    
    PC -->|"(1) Petición opencti.ryoiki"| WG
    WG -->|"(2) Consulta DNS"| DNS
    DNS -->|"(3) Resuelve 10.0.0.2"| WG
    WG -->|"(4) Tráfico Web"| FW
    FW --> OCTI
```

