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
    echo "Creando entorno virtual..."
    python3 -m venv venv
    echo "✓ Entorno virtual creado"
fi

# Activar entorno virtual
echo ""
echo "Activando entorno virtual..."
source venv/bin/activate

# Instalar/actualizar dependencias
echo ""
echo "Instalando dependencias..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✓ Dependencias instaladas"

# Crear directorios necesarios
mkdir -p received_files
mkdir -p uploads

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
