@echo off
title NMTBot
cd /d "%~dp0"
echo Iniciando NMTBot...
py main.py
if errorlevel 1 (
    echo.
echo Erro: nao foi possivel iniciar o bot.
echo Verifique se o Python esta instalado e se as dependencias foram instaladas.
echo Rode install_deps.bat para instalar as dependencias.
    pause
)
pause
