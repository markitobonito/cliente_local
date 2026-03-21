#!/bin/bash
# Script de inicio para macOS

echo "=========================================="
echo "  LAN File Transfer - Cliente (macOS)"
echo "=========================================="
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 no está instalado"
    echo "Instala Python desde: https://www.python.org/downloads/"
    exit 1
fi

echo "✓ Python encontrado: $(python3 --version)"

# Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo ""
    echo "⚠️  Creando entorno virtual (requiere internet)..."
    python3 -m venv venv
    echo "✓ Entorno virtual creado"
    NEED_INSTALL=true
else
    echo "✓ Entorno virtual ya existe"
    NEED_INSTALL=false
fi

# Activar entorno virtual
echo ""
echo "Activando entorno virtual..."
source venv/bin/activate

# Instalar dependencias solo si es necesario
if [ "$NEED_INSTALL" = true ]; then
    echo ""
    echo "⚠️  Instalando dependencias (requiere internet)..."
    echo "Si no tienes internet, presiona Ctrl+C y conéctate primero."
    echo ""
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    echo "✓ Dependencias instaladas"
    echo ""
    echo "Ahora puedes desconectarte de internet y conectarte"
    echo "a la red del sistema. Luego ejecuta el script nuevamente."
    exit 0
fi

# Crear directorios necesarios
mkdir -p received_files
mkdir -p uploads

# Detectar red actual
echo ""
echo "=========================================="
echo "  Verificando red..."
echo "=========================================="
CURRENT_IP=$(python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); print(s.getsockname()[0]); s.close()" 2>/dev/null)

if [ -n "$CURRENT_IP" ]; then
    echo "✓ IP detectada: $CURRENT_IP"
    echo ""
    echo "⚠️  IMPORTANTE:"
    echo "   El cliente se iniciará con esta IP."
    echo "   Si cambias de red después, el multicast"
    echo "   NO funcionará. Deberás reiniciar el script."
    echo ""
else
    echo "⚠️  No se pudo detectar IP (sin conexión)"
    echo ""
fi

read -p "¿Estás en la red del sistema? (s/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[SsYy]$ ]]; then
    echo ""
    echo "Cambia a la red del sistema y ejecuta el script nuevamente."
    exit 0
fi

# Ejecutar cliente
echo ""
echo "=========================================="
echo "  Iniciando cliente..."
echo "=========================================="
echo ""
echo "Interfaz web: http://localhost:1492"
echo "Presiona Ctrl+C para detener"
echo ""

python client.py
