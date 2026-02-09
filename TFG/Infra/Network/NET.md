![[Pasted image 20251220200644.png]]
![[Pasted image 20251220200744.png]]
![[Pasted image 20251220200806.png]]
![[Pasted image 20251220200856.png]]

![[Pasted image 20260107184228.png]]
Routing forward  del router
![[WhatsApp Image 2026-01-07 at 18.54.53.jpeg]]


```mermaid

graph TD

    subgraph "Cliente Remoto (Tu PC)"

        Termius[Termius App]

    end

  

    subgraph "OVH Bare Metal Server"

        Physical[NIC Fisica enp]

        subgraph "Proxmox VE Host"

            vmbr0[Bridge Público vmbr0]

            SSH_PVE[Servicio SSH Puerto 22]

            GUI_PVE[Web GUI Puerto 8006]

            subgraph "VM: OPNsense (Router/Firewall)"

                WAN[WAN Interface]

                LAN[LAN Interface]

            end

            vmbr1[Bridge Privado vmbr1 10.10.10.x]

            subgraph "Zona Segura (LAN)"

                OpenCTI[VM OpenCTI Stack]

                Wazuh[VM Wazuh SIEM]

            end

        end

    end

  

    Termius -->|1. Túnel SSH Puerto 22| SSH_PVE

    SSH_PVE -.->|2. Port Forwarding Local| GUI_PVE

    Physical --> vmbr0

    vmbr0 --> WAN

    WAN -->|NAT/Reglas| LAN

    LAN --> vmbr1

    vmbr1 --> OpenCTI

    vmbr1 --> Wazuh
```