#!/bin/bash
# TaskMiner - demonstração (macOS/Linux): instala, sobe o painel e abre o Chrome
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements.txt || { echo "Falha ao instalar dependências."; exit 1; }
( sleep 10; open -a "Google Chrome" http://localhost:5000/entrar 2>/dev/null || xdg-open http://localhost:5000/entrar 2>/dev/null || open http://localhost:5000/entrar ) &
python3 main.py demo
