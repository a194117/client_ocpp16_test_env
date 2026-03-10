#!/bin/bash
# scripts/run_debug.sh

# Carrega configurações do .env se existir
if [ -f ../config/.env ]; then
    export $(cat ../config/.env | grep -v '#' | xargs)
fi

cd "$(dirname "$0")/.."
python3 -m pudb main.py