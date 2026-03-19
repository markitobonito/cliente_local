# Localcito - Sistema de Transferencia de Archivos LAN

Sistema completo de transferencia de archivos en red local con descubrimiento automático, interfaz web, alertas TTS y reproducción programada de videos.

## Arquitectura

El sistema consta de dos componentes independientes:

- **Cliente**: Máquinas que envían y reciben archivos, con interfaz web en puerto 1492
- **Puente**: Servidor central que recibe archivos y los distribuye a todos los clientes

### Protocolo de Comunicación

1. **Descubrimiento (Multicast UDP)**
   - Grupo: 239.255.255.250:4000
   - Cliente envía: HELLO|<ip> (al iniciar) y ALIVE|<ip> (cada 5s)
   - Puente envía: BRIDGE|<ip> (cada 3s)

2. **Transferencia de Archivos (QUIC/UDP)**
   - Puerto: 5000
   - Formato: filename\0file_data
   - Cliente → Puente → Todos los clientes (excepto remitente)

## Despliegue

### Opción 1: Docker en Linux (Producción - RECOMENDADO)

Para máquinas Linux separadas en la misma LAN física:

**En el servidor puente:**
```bash
cd localcito/puente
docker compose -f docker-compose.prod.yml up -d
```

**En cada servidor cliente:**
```bash
cd localcito/cliente
docker compose -f docker-compose.prod.yml up -d
```

Accede a la interfaz web: `http://<ip-cliente>:1492`

### Opción 2: Python Nativo en macOS/Windows

Docker Desktop en Mac/Windows no soporta multicast entre máquinas físicas. Usa Python directamente:

**macOS:**
```bash
cd localcito/cliente
chmod +x start_macos.sh
./start_macos.sh
```

**Windows:**
```cmd
cd localcito\cliente
start_windows.bat
```

Accede a la interfaz web: `http://localhost:1492`

📖 **Guía completa**: Ver [INSTALL_MACOS_WINDOWS.md](INSTALL_MACOS_WINDOWS.md)

### Opción 3: Desarrollo Local (Ambos contenedores en misma máquina)

Solo para pruebas en una sola máquina:

```bash
# Inicia el puente
cd localcito/puente
docker compose up -d

# Inicia el cliente
cd localcito/cliente
docker compose up -d
```

Accede a la interfaz web: `http://localhost:1492`

### Arquitectura Recomendada para Producción

```
┌─────────────────────────────────────────────────┐
│  Puente (Bridge)                                │
│  - Máquina: Linux                               │
│  - Ejecución: docker-compose.prod.yml          │
│  - IP: 192.168.1.100                           │
└─────────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
┌───────▼──────┐ ┌───▼──────┐ ┌───▼──────┐
│ Cliente 1    │ │Cliente 2 │ │Cliente 3 │
│ Linux        │ │macOS     │ │Windows   │
│ Docker       │ │Python    │ │Python    │
│ prod.yml     │ │nativo    │ │nativo    │
└──────────────┘ └──────────┘ └──────────┘
```

### Notas Importantes

- **Atributo `version`**: Ya no es necesario en Docker Compose v2, ha sido eliminado
- **Redes Docker**: 
  - Desarrollo: Usa red compartida `localcito-network` para comunicación entre contenedores en misma máquina
  - Producción: Usa `network_mode: host` para acceso directo a la red física
- **Multicast**: Asegúrate de que tu red soporte multicast UDP (grupo 239.255.255.250:4000)
- **Firewall**: Permite tráfico UDP en puertos 4000 (multicast) y 5000 (QUIC), TCP 1492 (Flask)

## Funcionalidades

### Transferencia de Archivos
- Subir archivos desde interfaz web
- Distribución automática a todos los clientes
- Límite: 100MB por archivo

### Alertas TTS
- Enviar mensajes de texto con repeticiones (1-10)
- Reproducción automática con text-to-speech
- Notificaciones de escritorio

### Videos
- **Inmediato**: Reproducción con audio al recibir
- **Silencioso**: Reproducción sin audio (flag .SILENT)
- **Programado**: Reproducción en horarios específicos (flag .SCHED_HH:MM_días)

## Requisitos de Red

- Multicast habilitado en la red local
- Puertos abiertos:
  - UDP 4000 (multicast)
  - UDP 5000 (QUIC)
  - TCP 1492 (Flask, solo cliente)
- Firewall configurado para permitir tráfico multicast y QUIC

## Estructura del Proyecto

```
localcito/
├── cliente/              # Componente cliente
│   ├── app.py           # Flask web interface
│   ├── client.py        # Coordinador principal
│   ├── discovery.py     # Descubrimiento multicast
│   ├── quic_sender.py   # Envío QUIC
│   ├── quic_receiver.py # Recepción QUIC
│   ├── msg_monitor.py   # Monitor de alertas TTS
│   ├── video_monitor.py # Monitor de videos
│   ├── config.py        # Configuración
│   ├── utils.py         # Utilidades
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── templates/
│       └── index.html   # Interfaz web
└── puente/              # Componente puente
    ├── bridge.py        # Coordinador principal
    ├── multicast_listener.py
    ├── multicast_announcer.py
    ├── client_table.py  # Tabla de clientes activos
    ├── quic_receiver.py # Recepción QUIC
    ├── quic_forwarder.py # Reenvío QUIC
    ├── config.py
    ├── utils.py
    ├── Dockerfile
    ├── docker-compose.yml
    └── requirements.txt
```

## Logs

Ver logs del cliente:
```bash
cd localcito/cliente
docker-compose logs -f
```

Ver logs del puente:
```bash
cd localcito/puente
docker-compose logs -f
```

## Documentación Adicional

- [Cliente README](cliente/README.md)
- [Puente README](puente/README.md)
- [Arquitectura](ARCHITECTURE.md)
- [Arquitectura de Red](NETWORK_ARCHITECTURE.md) - Explica por qué aparece 172.x.x.x y cómo funciona multicast
- [Troubleshooting](TROUBLESHOOTING.md)
- [Instalación macOS/Windows](INSTALL_MACOS_WINDOWS.md)
