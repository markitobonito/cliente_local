@echo off
REM Script de inicio para Windows

echo ==========================================
echo   LAN File Transfer - Cliente (Windows)
echo ==========================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python no esta instalado
    echo Instala Python desde: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python encontrado
python --version

REM Crear entorno virtual si no existe
if not exist "venv" (
    echo.
    echo Creando entorno virtual...
    python -m venv venv
    echo Entorno virtual creado
)

REM Activar entorno virtual
echo.
echo Activando entorno virtual...
call venv\Scripts\activate.bat

REM Instalar/actualizar dependencias
echo.
echo Instalando dependencias...
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
echo Dependencias instaladas

REM Crear directorios necesarios
if not exist "received_files" mkdir received_files
if not exist "uploads" mkdir uploads

REM Ejecutar cliente
echo.
echo ==========================================
echo   Iniciando cliente...
echo ==========================================
echo.
echo Interfaz web: http://localhost:1492
echo Presiona Ctrl+C para detener
echo.

python client.py
