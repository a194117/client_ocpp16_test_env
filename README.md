# OCPP Test Environment

Ambiente para simulação de um cliente OCPP 1.6 e testes de transações com o servidor SteVe.

## Pré-requisitos

- Python 3.10+
- Servidor SteVe rodando em `localhost:8080` (ou configurado via `.env`)
- WSL (opcional, para executar scripts shell)

## Instalação

```bash
git clone https://github.com/a194117/client_ocpp16_test_env.git
cd ocpp-test-env
python3 -m venv venv
source venv/bin/activate  
pip install -r requirements.txt
cp config/.env.example config/.env
# Edite config/.env com suas configurações
```

## Execute

```bash
./scripts/run_interactive.sh
