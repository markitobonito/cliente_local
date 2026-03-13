# Guía de Troubleshooting

## Problemas de Descubrimiento

### Los clientes no descubren el puente

**Síntomas**: Cliente muestra "Waiting for bridge announcement..." indefinidamente

**Diagnóstico**:
```bash
# Ver logs del cliente
cd localcito/cliente
docker-compose logs -f | grep "BRIDGE\|discovery"

# Ver logs del puente
cd localcito/puente
docker-compose logs -f | grep "BRIDGE\|announcer"
```

**Soluciones**:

1. **Verificar que el puente esté corriendo**:
```bash
cd localcito/puente
docker-compose ps
# Debe mostrar: localcito-puente (Up)
```

2. **Verificar multicast en la red**:
   - Multicast debe estar habilitado en el router/switch
   - Clientes y puente deben estar en la misma subred
   - Algunos routers bloquean multicast por defecto

3. **Verificar firewall**:
```bash
# macOS - verificar reglas
sudo pfctl -s rules | grep 4000

# Linux - verificar iptables
sudo iptables -L | grep 4000
```

4. **Reiniciar servicios**:
```bash
# Puente
cd localcito/puente
docker-compose restart

# Cliente
cd localcito/cliente
docker-compose restart
```

### Clientes se marcan como inactivos

**Síntomas**: Logs del puente muestran "Cleanup removed N inactive client(s)"

**Diagnóstico**:
```bash
# Ver heartbeat del cliente
docker-compose logs -f | grep ALIVE

# Ver tabla de clientes activos en puente
docker-compose logs -f | grep "Active clients"
```

**Soluciones**:

1. **Verificar heartbeat del cliente**:
   - Debe enviar ALIVE cada 5 segundos
   - Si no envía, reiniciar cliente

2. **Verificar timeout del puente**:
   - Por defecto: 10 segundos
   - Si la red tiene latencia alta, ajustar CLIENT_TIMEOUT en config.py

## Problemas de Transferencia

### Archivos no se transfieren

**Síntomas**: Archivo se sube en web pero no llega a otros clientes

**Diagnóstico**:
```bash
# Ver logs completos del flujo
# Cliente:
docker-compose logs -f | grep "send_file\|QUIC"

# Puente:
docker-compose logs -f | grep "Received file\|forward"
```

**Soluciones**:

1. **Verificar puerto QUIC (5000)**:
```bash
# Verificar que el puerto esté abierto
netstat -an | grep 5000

# macOS - abrir puerto en firewall
sudo pfctl -f /etc/pf.conf
```

2. **Verificar que el cliente tenga IP del puente**:
```bash
# En logs del cliente buscar:
# "Bridge discovered at: <ip>"
```

3. **Verificar conectividad QUIC**:
   - QUIC usa UDP, no TCP
   - Algunos firewalls bloquean UDP por defecto
   - Verificar que no haya NAT entre cliente y puente

### Archivos llegan corruptos

**Síntomas**: Archivos se reciben pero no se pueden abrir

**Diagnóstico**:
```bash
# Comparar tamaños
ls -lh /path/to/original
ls -lh ./received_files/
```

**Soluciones**:

1. **Verificar límite de tamaño**:
   - Máximo: 100MB por archivo
   - Archivos más grandes se rechazan

2. **Verificar logs de errores**:
```bash
docker-compose logs -f | grep "error\|Error\|ERROR"
```

## Problemas de Interfaz Web

### No se puede acceder a http://localhost:1492

**Síntomas**: Navegador muestra "Connection refused" o timeout

**Diagnóstico**:
```bash
# Verificar que Flask esté corriendo
docker-compose logs -f | grep Flask

# Verificar puerto
lsof -i :1492
```

**Soluciones**:

1. **Verificar contenedor**:
```bash
docker-compose ps
# Debe mostrar: localcito-cliente (Up)
```

2. **Verificar network_mode**:
```bash
# En docker-compose.yml debe tener:
# network_mode: host
```

3. **Probar desde otra máquina**:
```bash
# Reemplazar localhost con IP del cliente
http://<client-ip>:1492
```

### Formularios no responden

**Síntomas**: Al enviar formulario no pasa nada

**Diagnóstico**:
- Abrir consola del navegador (F12)
- Ver errores de JavaScript o red

**Soluciones**:

1. **Verificar JavaScript**:
   - Recargar página con Ctrl+Shift+R
   - Verificar que no haya errores en consola

2. **Verificar endpoints de Flask**:
```bash
docker-compose logs -f | grep "POST\|GET"
```

## Problemas de Alertas TTS

### Alertas no suenan

**Síntomas**: Archivo .msg se recibe pero no se reproduce audio

**Diagnóstico**:
```bash
# Ver logs del monitor
docker-compose logs -f | grep msg_monitor
```

**Soluciones**:

1. **Verificar pyttsx3**:
```bash
# Probar TTS manualmente
docker exec -it localcito-cliente python3 << EOF
import pyttsx3
engine = pyttsx3.init()
engine.say("Prueba de audio")
engine.runAndWait()
EOF
```

2. **Verificar formato del archivo**:
   - Formato correcto: `3|Mensaje de prueba`
   - Repeticiones: 1-10
   - Separador: pipe `|`

3. **Verificar sistema de audio**:
   - Docker debe tener acceso al sistema de audio del host
   - En macOS/Linux puede requerir configuración adicional

### Notificaciones no aparecen

**Síntomas**: TTS funciona pero no hay notificación de escritorio

**Soluciones**:

1. **Verificar plyer**:
```bash
docker exec -it localcito-cliente python3 -c "from plyer import notification; notification.notify(title='Test', message='Test')"
```

2. **Permisos de notificaciones**:
   - Verificar que el sistema permita notificaciones
   - En macOS: System Preferences → Notifications

## Problemas de Videos

### Videos no se reproducen

**Síntomas**: Archivo de video se recibe pero no se reproduce

**Diagnóstico**:
```bash
# Ver logs del monitor de videos
docker-compose logs -f | grep video_monitor
```

**Soluciones**:

1. **Verificar VLC/MPV**:
```bash
# Verificar instalación
docker exec -it localcito-cliente which vlc
docker exec -it localcito-cliente which mpv

# Probar reproducción manual
docker exec -it localcito-cliente vlc --play-and-exit /path/to/test.mp4
```

2. **Verificar formato de video**:
   - Formatos soportados: .mp4, .avi, .mkv, .mov
   - Codecs: H.264, H.265, VP9

3. **Verificar permisos de display**:
   - Docker necesita acceso al display del host
   - Configurar DISPLAY environment variable

### Videos programados no se ejecutan

**Síntomas**: Video con flag SCHED no se reproduce en el horario

**Diagnóstico**:
```bash
# Ver logs del scheduler
docker-compose logs -f | grep "schedule\|APScheduler"
```

**Soluciones**:

1. **Verificar formato del flag**:
   - Correcto: `video.SCHED_14:30_1,3,5.mp4`
   - Hora: HH:MM (24 horas)
   - Días: 1-7 (1=Lunes, 7=Domingo)

2. **Verificar APScheduler**:
```bash
# Ver jobs programados en logs
docker-compose logs | grep "Video scheduled"
```

3. **Verificar zona horaria**:
   - Docker usa UTC por defecto
   - Ajustar TZ environment variable si es necesario

## Comandos de Diagnóstico

### Ver estado general
```bash
# Cliente
cd localcito/cliente
docker-compose ps
docker-compose logs --tail=50

# Puente
cd localcito/puente
docker-compose ps
docker-compose logs --tail=50
```

### Verificar conectividad de red
```bash
# Ping entre cliente y puente
ping <bridge-ip>

# Verificar rutas multicast
netstat -g

# Verificar interfaces de red
ifconfig
```

### Limpiar y reiniciar
```bash
# Detener todo
docker-compose down

# Limpiar volúmenes y caché
docker-compose down -v
docker system prune -f

# Reconstruir desde cero
docker-compose build --no-cache
docker-compose up -d
```

### Modo debug
```bash
# Ejecutar en foreground para ver logs en tiempo real
docker-compose up

# Ver logs de un servicio específico
docker-compose logs -f cliente
docker-compose logs -f puente
```

## Problemas Conocidos

### Multicast en Docker Desktop (macOS/Windows)

Docker Desktop tiene limitaciones con multicast. Soluciones:

1. **Usar network_mode: host** (ya configurado)
2. **Ejecutar fuera de Docker** para pruebas:
```bash
cd localcito/cliente
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 client.py
```

### Puerto 1492 ocupado

Si otro servicio usa el puerto 1492:

1. **Cambiar puerto en config.py**:
```python
FLASK_PORT = 8080  # O cualquier puerto libre
```

2. **Reconstruir contenedor**:
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

### Permisos de archivos

Si hay errores de permisos al guardar archivos:

```bash
# Verificar permisos del directorio
ls -la received_files/

# Ajustar permisos
chmod 755 received_files/
```

## Contacto

Para problemas no resueltos, revisar:
- Logs completos: `docker-compose logs --tail=200`
- Documentación de arquitectura: `ARCHITECTURE.md`
- README del componente: `cliente/README.md` o `puente/README.md`
