# store/state.py
from dataclasses import dataclass, field
import threading
from functools import wraps
from typing import List
from ocpp.v16 import enums
from ocpp.v16 import datatypes  # importa as dataclasses fornecidas

def locked(func):
    """
    Define o decorator que recebe a função original (func) como argumento.  Em vez de escrever with self._lock dentro de cada método, o decorator faz isso automaticamente.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            # Ativamos uma "bandeira" interna para permitir a escrita temporariamente
            self._allow_write = True
            try:
                return func(self, *args, **kwargs)
            finally:
                self._allow_write = False
    return wrapper

@dataclass
class ChargePointState:
    """
    Estado global do Charge Point.
    """
    # Status básico do CP
    status: enums.ChargePointStatus = enums.ChargePointStatus.available
    error_code: enums.ChargePointErrorCode = enums.ChargePointErrorCode.no_error
    info: str | None = None

    # Lista de autorizações locais (local auth list)
    local_auth_list: List[datatypes.AuthorizationData] = field(default_factory=list)
    local_auth_list_version: int = 0

    # Perfis de carregamento ativos (TxProfile, ChargePointMaxProfile, etc.)
    charging_profiles: List[datatypes.ChargingProfile] = field(default_factory=list)

    # Transação atual (se houver)
    current_transaction_id: int | None = None
    current_connector_id: int | None = None
    id_tag_in_transaction: str | None = None

    # Reservas ativas
    reservations: List[dict] = field(default_factory=list)  # Você pode criar uma dataclass Reservation se desejar

    # Configurações do CP (key-value)
    configuration: dict = field(default_factory=dict)

    # ... adicione outros atributos conforme necessário

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    # Controla se a escrita está autorizada no momento
    _allow_write: bool = field(default=False, init=False, repr=False)

    def __setattr__(self, name, value):
        # 1. Permitir a criação inicial dos atributos e do próprio lock/bandeira
        if name in ("_lock", "_allow_write") or not hasattr(self, "_lock"):
            super().__setattr__(name, value)
            return

        # 2. Bloquear se tentar mudar diretamente sem passar pelo 'update'
        if not getattr(self, "_allow_write", False):
            raise AttributeError(
                f"Não é permitido modificar '{name}' diretamente. Use o método update()."
            )
        
        super().__setattr__(name, value)


    """       !!!! A IMPLEMENTAR !!!!
    
    def __post_init__(self):
        #Inicializa valores padrão complexos se necessário.
        with self._lock:
            if not self.configuration:
                # Carregar configurações iniciais (ex: de um arquivo)
                self.configuration = {
                    enums.ConfigurationKey.heartbeat_interval: 60,
                    enums.ConfigurationKey.authorization_cache_enabled: True,
                    # ...
                }
    """
    
    @locked
    def update(self, **kwargs):
        """Única porta de entrada para modificações externas."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    @locked
    def reset(self):
        """
        Reset Dinâmico da Classe. Percorre todos os campos da classe e atribui a eles o valor de uma nova instância "limpa". Usa o decorator @locked para garantir que ninguém lê/escreve enquanto as propriedades voltam ao padrão.

        """

        default_instance = self.__class__()
        
        for f in fields(self):
            # Para não perder a referência ao _lock de cada propriedade!
            if f.name == "_lock":
                continue
                
            val = getattr(default_instance, f.name)
            setattr(self, f.name, val)



# Criamos uma única instância global deste estado
state = ChargePointState()