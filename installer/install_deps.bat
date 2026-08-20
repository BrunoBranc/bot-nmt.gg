@echo off
title NMTBot - Instalando Dependencias
cd /d "%~dp0"
echo ============================================
echo   NMTBot - Instalacao de Dependencias
echo ============================================
echo.
echo Instalando pacotes Python...
py -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Falha ao instalar dependencias.
    pause
    exit /b 1
)
echo.
echo Instalando Chromium do Playwright...
py -m playwright install chromium
if errorlevel 1 (
    echo.
    echo Falha ao instalar Chromium.
    pause
    exit /b 1
)
echo.
echo ============================================
echo   Dependencias instaladas com sucesso!
echo ============================================
echo Agora voce pode iniciar o NMTBot.
echo.
pause
