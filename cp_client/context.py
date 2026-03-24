# cp_client/context.py
import contextvars

# Definição das variáveis de contexto (com valor padrão None)
connector_id: contextvars.ContextVar = contextvars.ContextVar('connector_id', default=None)
transaction_id: contextvars.ContextVar = contextvars.ContextVar('transaction_id', default=None)

# Funções auxiliares para manipulação segura
def set_connector_id(value):
    connector_id.set(value)

def get_connector_id():
    return connector_id.get()

def set_transaction_id(value):
    transaction_id.set(value)

def get_transaction_id():
    return transaction_id.get()
