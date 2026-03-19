#!/bin/bash
# Script de diagnóstico de red para LAN File Transfer System

echo "=========================================="
echo "Diagnóstico de Red - Localcito"
echo "=========================================="
echo ""

# Detectar sistema operativo
OS=$(uname -s)
echo "Sistema Operativo: $OS"
echo ""

# Detectar IP local
echo "1. Detectando IP local..."
if [ "$OS" = "Darwin" ]; then
    # macOS
    LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
elif [ "$OS" = "Linux" ]; then
    # Linux
    LOCAL_IP=$(hostname -I | awk '{print $1}')
else
    # Windows (Git Bash)
    LOCAL_IP=$(ipconfig | grep "IPv4" | head -1 | awk '{print $NF}')
fi

if [ -z "$LOCAL_IP" ]; then
    echo "❌ No se pudo detectar IP local"
else
    echo "✓ IP Local: $LOCAL_IP"
    
    # Verificar si es IP física (192.x o 10.x) o virtual (172.x)
    if [[ $LOCAL_IP == 192.* ]] || [[ $LOCAL_IP == 10.* ]]; then
        echo "✓ IP física detectada (red LAN)"
    elif [[ $LOCAL_IP == 172.* ]]; then
        echo "⚠️  IP virtual detectada (red Docker)"
        echo "   Multicast NO funcionará entre máquinas físicas"
    fi
fi
echo ""

# Verificar Docker
echo "2. Verificando Docker..."
if command -v docker &> /dev/null; then
    echo "✓ Docker instalado: $(docker --version)"
    
    # Verificar Docker Compose
    if docker compose version &> /dev/null; then
        echo "✓ Docker Compose v2 instalado"
    elif docker-compose --version &> /dev/null; then
        echo "⚠️  Docker Compose v1 instalado (obsoleto)"
        echo "   Recomendación: Actualizar a Docker Compose v2"
    else
        echo "❌ Docker Compose no instalado"
    fi
else
    echo "❌ Docker no instalado"
fi
echo ""

# Verificar Python
echo "3. Verificando Python..."
if command -v python3 &> /dev/null; then
    echo "✓ Python3 instalado: $(python3 --version)"
else
    echo "❌ Python3 no instalado"
fi
echo ""

# Verificar contenedores corriendo
echo "4. Verificando contenedores..."
if command -v docker &> /dev/null; then
    PUENTE_RUNNING=$(docker ps --filter "name=puente" --format "{{.Names}}" 2>/dev/null)
    CLIENTE_RUNNING=$(docker ps --filter "name=cliente" --format "{{.Names}}" 2>/dev/null)
    
    if [ -n "$PUENTE_RUNNING" ]; then
        echo "✓ Puente corriendo: $PUENTE_RUNNING"
        
        # Obtener IP del contenedor puente
        PUENTE_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $PUENTE_RUNNING 2>/dev/null)
        if [ -n "$PUENTE_IP" ]; then
            echo "  IP del contenedor: $PUENTE_IP"
            if [[ $PUENTE_IP == 172.* ]]; then
                echo "  ⚠️  Contenedor en red virtual (172.x.x.x)"
                echo "     Para producción, usar docker-compose.prod.yml con network_mode: host"
            fi
        fi
    else
        echo "⚠️  Puente no está corriendo"
    fi
    
    if [ -n "$CLIENTE_RUNNING" ]; then
        echo "✓ Cliente corriendo: $CLIENTE_RUNNING"
        
        # Obtener IP del contenedor cliente
        CLIENTE_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $CLIENTE_RUNNING 2>/dev/null)
        if [ -n "$CLIENTE_IP" ]; then
            echo "  IP del contenedor: $CLIENTE_IP"
            if [[ $CLIENTE_IP == 172.* ]]; then
                echo "  ⚠️  Contenedor en red virtual (172.x.x.x)"
                echo "     Para producción, usar docker-compose.prod.yml con network_mode: host"
            fi
        fi
    else
        echo "⚠️  Cliente no está corriendo"
    fi
else
    echo "⚠️  Docker no disponible, no se pueden verificar contenedores"
fi
echo ""

# Verificar puertos
echo "5. Verificando puertos..."
if command -v netstat &> /dev/null; then
    # Puerto multicast (4000)
    if netstat -an 2>/dev/null | grep -q ":4000"; then
        echo "✓ Puerto 4000 (multicast) en uso"
    else
        echo "⚠️  Puerto 4000 (multicast) no está en uso"
    fi
    
    # Puerto QUIC (5000)
    if netstat -an 2>/dev/null | grep -q ":5000"; then
        echo "✓ Puerto 5000 (QUIC) en uso"
    else
        echo "⚠️  Puerto 5000 (QUIC) no está en uso"
    fi
    
    # Puerto Flask (1492)
    if netstat -an 2>/dev/null | grep -q ":1492"; then
        echo "✓ Puerto 1492 (Flask) en uso"
    else
        echo "⚠️  Puerto 1492 (Flask) no está en uso"
    fi
else
    echo "⚠️  netstat no disponible, no se pueden verificar puertos"
fi
echo ""

# Recomendaciones
echo "=========================================="
echo "Recomendaciones"
echo "=========================================="
echo ""

if [ "$OS" = "Darwin" ]; then
    echo "macOS detectado:"
    echo "  - Docker Desktop NO soporta multicast entre máquinas físicas"
    echo "  - Recomendación: Ejecutar Python nativo"
    echo "  - Comando: cd localcito/cliente && ./start_macos.sh"
    echo ""
elif [ "$OS" = "Linux" ]; then
    echo "Linux detectado:"
    echo "  - Usar docker-compose.prod.yml con network_mode: host"
    echo "  - Comando: docker compose -f docker-compose.prod.yml up -d"
    echo ""
else
    echo "Windows detectado:"
    echo "  - Docker Desktop NO soporta multicast entre máquinas físicas"
    echo "  - Recomendación: Ejecutar Python nativo"
    echo "  - Comando: cd localcito\\cliente && start_windows.bat"
    echo ""
fi

echo "Documentación:"
echo "  - Arquitectura de red: localcito/NETWORK_ARCHITECTURE.md"
echo "  - Troubleshooting: localcito/TROUBLESHOOTING.md"
echo "  - Instalación Mac/Windows: localcito/INSTALL_MACOS_WINDOWS.md"
echo ""
