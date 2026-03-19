# Arquitectura de Red - LAN File Transfer System

## Problema: ¿Por qué aparece 172.x.x.x en lugar de 192.x.x.x?

### Redes Docker vs Redes Físicas

Cuando ejecutas Docker, crea **redes virtuales** separadas de tu red física:

```
Red Física (LAN):
├── Router: 192.168.1.1
├── Laptop 1: 192.168.1.100
├── Laptop 2: 192.168.1.101
└── Laptop 3: 192.168.1.102

Red Virtual Docker (Bridge):
├── Docker Network 1: 172.17.0.0/16
│   └── Container A: 172.17.0.2
├── Docker Network 2: 172.18.0.0/16
│   └── Container B: 172.18.0.2
└── Docker Network 3: 172.19.0.0/16
    └── Container C: 172.19.0.2
```

### ¿Por qué no puede usar 192.x.x.x directamente?

Docker **aísla** los contenedores de la red física por seguridad. Los contenedores:
- Obtienen IPs virtuales (172.x.x.x)
- Se comunican a través de un "puente" (bridge) virtual
- NO tienen acceso directo a la red física (192.x.x.x)

### El Problema con Multicast

**Multicast** es un protocolo que envía mensajes a múltiples destinatarios en la misma red física. Pero:

1. **Docker bridge networks están aisladas**: Los paquetes multicast NO pueden salir de la red virtual (172.x.x.x) hacia la red física (192.x.x.x)

2. **Cada contenedor está en su propia red**: Si tienes 3 clientes en Docker, cada uno puede estar en una red diferente:
   - Cliente 1: 172.19.0.2
   - Cliente 2: 172.20.0.2
   - Cliente 3: 172.21.0.2
   
   Estos contenedores **NO pueden verse entre sí** con multicast.

3. **El puente tampoco puede alcanzarlos**: Si el puente está en 172.17.0.2, no puede enviar multicast a 172.19.0.2 o 172.20.0.2.

## Soluciones por Sistema Operativo

### Linux: `network_mode: host`

En Linux, Docker puede usar `network_mode: host` para dar acceso directo a la red física:

```yaml
services:
  puente:
    network_mode: host  # Contenedor usa red física directamente
```

Con esto:
- El contenedor obtiene la IP física (192.168.1.50)
- Multicast funciona correctamente
- Todos los contenedores se ven entre sí

**Usar**: `docker-compose.prod.yml` en Linux

### macOS/Windows: Python Nativo (NO Docker)

En Mac/Windows, Docker Desktop corre en una **máquina virtual**:

```
Mac/Windows Host (192.168.1.100)
└── Docker Desktop VM (192.168.65.2)
    └── Contenedor (172.17.0.2)
```

Cuando usas `network_mode: host`:
- El contenedor accede a la red de la VM (192.168.65.2)
- NO accede a la red física del Mac (192.168.1.100)
- Multicast queda atrapado en la VM

**Solución**: Ejecutar Python directamente en el host (sin Docker):

```bash
# macOS
cd localcito/cliente
./start_macos.sh

# Windows
cd localcito\cliente
start_windows.bat
```

Esto ejecuta Python en el host, con acceso directo a la red física (192.168.1.100).

## Arquitectura Recomendada

### Opción 1: Todo en Linux (Producción)

```
Laptop 1 (Linux) - Puente
├── IP: 192.168.1.50
└── Docker con network_mode: host
    └── docker-compose.prod.yml

Laptop 2 (Linux) - Cliente
├── IP: 192.168.1.100
└── Docker con network_mode: host
    └── docker-compose.prod.yml

Laptop 3 (Linux) - Cliente
├── IP: 192.168.1.101
└── Docker con network_mode: host
    └── docker-compose.prod.yml
```

### Opción 2: Mixto (Desarrollo)

```
Laptop 1 (Linux) - Puente
├── IP: 192.168.1.50
└── Docker con network_mode: host
    └── docker-compose.prod.yml

Laptop 2 (macOS) - Cliente
├── IP: 192.168.1.100
└── Python nativo (sin Docker)
    └── ./start_macos.sh

Laptop 3 (Windows) - Cliente
├── IP: 192.168.1.101
└── Python nativo (sin Docker)
    └── start_windows.bat
```

### Opción 3: Desarrollo Local (Misma Máquina)

```
Laptop 1 (Linux/Mac/Windows)
├── Puente: Docker con port mapping
│   └── docker-compose.yml (bridge network)
└── Cliente: Docker con port mapping
    └── docker-compose.yml (bridge network)
```

**Nota**: Esta opción NO usa multicast real, solo sirve para desarrollo.

## Verificación de Red

### Verificar IP detectada

```bash
# Dentro del contenedor
docker exec -it localcito-cliente python3 -c "from utils import detect_local_ip; print(detect_local_ip())"

# Debe mostrar:
# Linux con host: 192.168.1.100 ✓
# Mac/Windows con host: 192.168.65.2 ✗ (IP de la VM)
# Mac/Windows nativo: 192.168.1.100 ✓
```

### Verificar multicast

```bash
# Ver logs del cliente
docker-compose logs -f | grep "Sent HELLO"

# Si NO aparece "Sent HELLO", multicast no funciona
# Si aparece "OSError 49", problema de permisos/red en Mac
```

### Verificar conectividad

```bash
# Desde el cliente, hacer ping al puente
ping 192.168.1.50

# Debe responder con la IP física, NO con 172.x.x.x
```

## Resumen

| Sistema Operativo | Solución | Comando |
|-------------------|----------|---------|
| Linux | Docker con `network_mode: host` | `docker compose -f docker-compose.prod.yml up -d` |
| macOS | Python nativo (sin Docker) | `./start_macos.sh` |
| Windows | Python nativo (sin Docker) | `start_windows.bat` |
| Desarrollo local | Docker con bridge network | `docker compose up -d` |

**Regla de oro**: Si ves IPs 172.x.x.x en los logs, multicast NO funcionará entre máquinas físicas diferentes.
