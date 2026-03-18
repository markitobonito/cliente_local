# Instalación sin Docker para macOS y Windows

Esta guía te permite ejecutar el sistema LAN File Transfer directamente con Python en macOS y Windows, sin usar Docker. Esto permite que el multicast funcione correctamente entre máquinas físicas.

## Requisitos Previos

- Python 3.9 o superior
- pip (gestor de paquetes de Python)

## Instalación en macOS

### 1. Verificar Python

```bash
python3 --version
```

Debe mostrar Python 3.9 o superior.

### 2. Clonar o copiar el proyecto

```bash
cd ~/Documents
# Copia la carpeta localcito/cliente aquí
```

### 3. Crear entorno virtual

```bash
cd localcito/cliente
python3 -m venv venv
source venv/bin/activate
```

### 4. Instalar dependencias

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Crear directorios necesarios

```bash
mkdir -p received_files
mkdir -p uploads
```

### 6. Ejecutar el cliente

```bash
python client.py
```

Deberías ver:
```
LAN File Transfer System - Client Starting
Client starting with local IP: 192.168.x.x
Flask web server started on http://0.0.0.0:1492
Waiting for bridge announcement...
```

### 7. Acceder a la interfaz web

Abre tu navegador en: `http://localhost:1492`

---

## Instalación en Windows

### 1. Verificar Python

Abre PowerShell o CMD y ejecuta:

```powershell
python --version
```

Debe mostrar Python 3.9 o superior. Si no tienes Python, descárgalo de: https://www.python.org/downloads/

**IMPORTANTE:** Durante la instalación, marca la opción "Add Python to PATH".

### 2. Clonar o copiar el proyecto

```powershell
cd C:\Users\TuUsuario\Documents
# Copia la carpeta localcito\cliente aquí
```

### 3. Crear entorno virtual

```powershell
cd localcito\cliente
python -m venv venv
venv\Scripts\activate
```

### 4. Instalar dependencias

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

**Nota para Windows:** Si `pyttsx3` da problemas, instala también:
```powershell
pip install pywin32
```

### 5. Crear directorios necesarios

```powershell
mkdir received_files
mkdir uploads
```

### 6. Ejecutar el cliente

```powershell
python client.py
```

Deberías ver:
```
LAN File Transfer System - Client Starting
Client starting with local IP: 192.168.x.x
Flask web server started on http://0.0.0.0:1492
Waiting for bridge announcement...
```

### 7. Acceder a la interfaz web

Abre tu navegador en: `http://localhost:1492`

---

## Solución de Problemas

### macOS: Permiso denegado para multicast

Si ves errores de permisos, ejecuta:

```bash
sudo python client.py
```

O configura permisos de firewall:
1. Ve a Preferencias del Sistema → Seguridad y Privacidad → Firewall
2. Haz clic en "Opciones de Firewall"
3. Agrega Python a las aplicaciones permitidas

### Windows: Firewall bloqueando conexiones

Si el cliente no se conecta al puente:

1. Abre "Windows Defender Firewall"
2. Haz clic en "Permitir una aplicación o característica a través de Windows Defender Firewall"
3. Haz clic en "Cambiar configuración" → "Permitir otra aplicación"
4. Busca y agrega `python.exe` (ubicado en `C:\Users\TuUsuario\AppData\Local\Programs\Python\Python3x\python.exe`)
5. Marca las casillas "Privada" y "Pública"

### Error: ModuleNotFoundError

Si ves errores de módulos faltantes:

```bash
# macOS/Linux
source venv/bin/activate
pip install -r requirements.txt

# Windows
venv\Scripts\activate
pip install -r requirements.txt
```

### El cliente no descubre el puente

Verifica que:
1. El puente esté corriendo en una máquina Linux con `docker-compose.prod.yml`
2. Ambas máquinas estén en la misma red física (mismo router/switch)
3. No haya VPNs activas que interfieran con el multicast
4. El firewall permita tráfico UDP en los puertos 4000 y 5000

---

## Ejecutar como Servicio (Opcional)

### macOS: Crear un Launch Agent

Crea el archivo `~/Library/LaunchAgents/com.localcito.cliente.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.localcito.cliente</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/TuUsuario/Documents/localcito/cliente/venv/bin/python</string>
        <string>/Users/TuUsuario/Documents/localcito/cliente/client.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/TuUsuario/Documents/localcito/cliente/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/TuUsuario/Documents/localcito/cliente/logs/stderr.log</string>
</dict>
</plist>
```

Luego:

```bash
mkdir -p ~/Documents/localcito/cliente/logs
launchctl load ~/Library/LaunchAgents/com.localcito.cliente.plist
```

### Windows: Crear un Servicio con NSSM

1. Descarga NSSM: https://nssm.cc/download
2. Extrae `nssm.exe` a `C:\nssm`
3. Abre PowerShell como Administrador:

```powershell
cd C:\nssm
.\nssm.exe install LocalcitoCliente "C:\Users\TuUsuario\Documents\localcito\cliente\venv\Scripts\python.exe" "C:\Users\TuUsuario\Documents\localcito\cliente\client.py"
.\nssm.exe start LocalcitoCliente
```

---

## Desinstalación

### macOS

```bash
# Detener el servicio (si lo configuraste)
launchctl unload ~/Library/LaunchAgents/com.localcito.cliente.plist
rm ~/Library/LaunchAgents/com.localcito.cliente.plist

# Eliminar archivos
cd ~/Documents
rm -rf localcito
```

### Windows

```powershell
# Detener el servicio (si lo configuraste)
C:\nssm\nssm.exe stop LocalcitoCliente
C:\nssm\nssm.exe remove LocalcitoCliente confirm

# Eliminar archivos
cd C:\Users\TuUsuario\Documents
Remove-Item -Recurse -Force localcito
```

---

## Arquitectura Recomendada

Para un sistema completo con máquinas mixtas:

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
│ prod.yml     │ │directo   │ │directo   │
└──────────────┘ └──────────┘ └──────────┘
```

---

## Soporte

Si tienes problemas, revisa los logs:

```bash
# macOS/Linux
tail -f ~/Documents/localcito/cliente/logs/stderr.log

# Windows
Get-Content C:\Users\TuUsuario\Documents\localcito\cliente\logs\stderr.log -Wait
```
