#!/bin/bash
# scripts/run_interactive.sh

# Carrega configurações do .env se existir
if [ -f ../config/.env ]; then
    export $(cat ../config/.env | grep -v '#' | xargs)
fi

cd "$(dirname "$0")/.."
python main.py