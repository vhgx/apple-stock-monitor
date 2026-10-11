#!/usr/bin/env bash
# Inicia o monitor em modo contínuo em segundo plano ou no terminal
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "Iniciando monitoramento de estoque Apple..."
python3 apple_monitor.py --loop --interval 5
