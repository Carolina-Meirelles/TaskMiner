@echo off
chcp 65001 >nul
title TaskMiner
cd /d "%~dp0"
echo.
echo  TaskMiner - demonstracao
echo  ------------------------
where python >nul 2>nul
if errorlevel 1 (
  echo  O Python nao esta instalado neste computador.
  echo  Instale em python.org marcando "Add Python to PATH" e rode este arquivo de novo.
  start "" https://www.python.org/downloads/
  pause
  exit /b 1
)
echo  Instalando dependencias (so demora na primeira vez)...
python -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo  Nao foi possivel instalar as dependencias. Verifique a internet e tente de novo.
  pause
  exit /b 1
)
echo  O Chrome vai abrir em alguns segundos. Para encerrar, feche esta janela.
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 10; try { Start-Process chrome http://localhost:5000/entrar -ErrorAction Stop } catch { Start-Process http://localhost:5000/entrar }"
python main.py demo
pause
