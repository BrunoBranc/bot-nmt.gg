@echo off
echo Gerando .exe do Bot NMT.gg...

python -m pip install pyinstaller --quiet

python -m PyInstaller ^
  --onefile ^
  --windowed ^
  --name "BotNMT" ^
  --add-data "data;data" ^
  --add-data "app;app" ^
  --hidden-import customtkinter ^
  --hidden-import socketio ^
  --hidden-import websocket ^
  --hidden-import playwright ^
  --icon "assets\nmt_bot_icon.ico" ^
  main.py

echo.
echo Pronto! O executavel esta em: dist\BotNMT.exe
pause
