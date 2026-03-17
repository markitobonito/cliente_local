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

### Desarrollo Local (macOS/Windows o Linux con ambos contenedores en misma máquina)

Usa la configuración por defecto con redes Docker:

**1. Inicia el puente primero:**
```bash
cd localcito/puente
docker compose up -d
```

**2. Luego inicia el cliente:**
```bash
cd localcito/cliente
docker compose up -d
```

**3. Accede a la interfaz web:**
```
http://localhost:1492
```

### Producción Linux (Máquinas Separadas)

Para mejor rendimiento en Linux con máquinas separadas, usa `network_mode: host`:

**1. Edita `docker-compose.yml` en cada máquina:**

En el servidor puente (`localcito/puente/docker-compose.yml`):
```yaml
services:
  puente:
    # Comentar estas líneas:
    # networks:
    #   - localcito
    # Descomentar esta línea:
    network_mode: host
```

En cada servidor cliente (`localcito/cliente/docker-compose.yml`):
```yaml
services:
  cliente:
    # Comentar estas líneas:
    # networks:
    #   - localcito
    # Descomentar esta línea:
    network_mode: host
```

**2. Inicia los contenedores:**
```bash
# En servidor puente
cd localcito/puente
docker compose up -d

# En cada servidor cliente
cd localcito/cliente
docker compose up -d
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
- [Troubleshooting](TROUBLESHOOTING.md)
