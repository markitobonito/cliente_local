# Arquitectura del Sistema

## Componentes

### Cliente
Cada máquina cliente ejecuta:
- **Discovery**: Envía HELLO/ALIVE, escucha BRIDGE
- **QUIC Sender**: Envía archivos al puente
- **QUIC Receiver**: Recibe archivos del puente (puerto 5000)
- **Flask Web**: Interfaz web para subir archivos (puerto 1492)
- **Message Monitor**: Procesa alertas .msg con TTS
- **Video Monitor**: Procesa videos con flags de reproducción

### Puente
Una máquina puente ejecuta:
- **Multicast Listener**: Recibe HELLO/ALIVE de clientes
- **Multicast Announcer**: Envía BRIDGE cada 3s
- **Client Table**: Mantiene tabla de clientes activos (timeout 10s)
- **QUIC Receiver**: Recibe archivos de clientes (puerto 5000)
- **QUIC Forwarder**: Distribuye archivos a todos los clientes excepto remitente

## Flujo de Datos

### Descubrimiento
```
Cliente: HELLO|192.168.1.100 → Multicast
Puente: Recibe HELLO → Agrega a tabla
Puente: BRIDGE|192.168.1.1 → Multicast (cada 3s)
Cliente: Recibe BRIDGE → Guarda IP del puente
Cliente: ALIVE|192.168.1.100 → Multicast (cada 5s)
Puente: Recibe ALIVE → Actualiza timestamp
```

### Transferencia de Archivos
```
Cliente A: Sube archivo en web → QUIC → Puente
Puente: Recibe archivo → Consulta tabla activa
Puente: QUIC → Cliente B, Cliente C, ... (paralelo)
Clientes: Reciben archivo → Guardan en received_files/
```

### Alertas TTS
```
Cliente A: Envía alerta "3|Reunión en 5 min" → .msg → Puente
Puente: Distribuye .msg a todos los clientes
Clientes: Detectan .msg → Parsean → TTS x3 → Eliminan archivo
```

### Videos
```
Cliente A: Sube video.mp4 → Puente
Puente: Distribuye a todos
Clientes: Detectan video → Reproducen inmediatamente

Cliente A: Sube video.SILENT.mp4 → Puente
Clientes: Reproducen sin audio

Cliente A: Sube video.SCHED_14:30_1,3,5.mp4 → Puente
Clientes: Programan para Lun/Mié/Vie a las 14:30
```

## Modelo de Threading

### Cliente
- Thread principal: Coordinación
- Thread discovery: Heartbeat + escucha BRIDGE
- Thread QUIC receiver: Acepta conexiones entrantes
- Thread Flask: Servidor web
- Thread msg_monitor: Escanea .msg cada 2s
- Thread video_monitor: Escanea videos cada 2s

### Puente
- Thread principal: Coordinación
- Thread multicast_listener: Recibe HELLO/ALIVE
- Thread multicast_announcer: Envía BRIDGE cada 3s
- Thread cleanup: Limpia clientes inactivos cada 2s
- Thread QUIC receiver: Acepta conexiones entrantes
- Thread logging: Log de clientes activos cada 10s
- ThreadPoolExecutor: Forwarding paralelo (max 10 workers)

## Protocolos

### Multicast Discovery
- Grupo: 239.255.255.250
- Puerto: 4000
- TTL: 1 (solo red local)
- Mensajes: HELLO|ip, ALIVE|ip, BRIDGE|ip

### QUIC File Transfer
- Puerto: 5000
- Protocolo: QUIC sobre UDP
- ALPN: "file-transfer"
- Formato mensaje: filename\0file_data
- Sin verificación de certificados (red local)

### Flask Web Interface
- Puerto: 1492
- Endpoints:
  - GET / → index.html
  - POST /api/upload → Subir archivo
  - POST /send-notification → Enviar alerta
  - POST /videos → Subir video con flags
