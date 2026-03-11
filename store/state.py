# store/state.py
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone, timedelta

import threading
from functools import wraps
from typing import List

from ocpp.v16 import enums
from ocpp.v16 import datatypes  # importa as dataclasses fornecidas

def locked(func):
    """
    decorador personalizado que envolve uma função para adquirir o lock antes de executá-la.
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
class ConnectorState:
    """Estado de um conector individual."""
    connector_id: int
    status: enums.ChargePointStatus = enums.ChargePointStatus.available
    error_code: enums.ChargePointErrorCode = enums.ChargePointErrorCode.no_error
    info: str | None = None
    timestamp: datetime | None = None,


@dataclass
class ChargePointState:
    """
    Estado global do Charge Point.
    """
    
    # Status básico do CP
    registration: enums.ChargePointStatus | None = None
    status: enums.ChargePointStatus = enums.ChargePointStatus.available
    error_code: enums.ChargePointErrorCode = enums.ChargePointErrorCode.no_error
    info: str | None = None
    
    # Conectores
    connectors_qty: int = 0
    connectors: List[ConnectorState] = field(default_factory=list)  
    
    # Relógio Interno para sincronização com o servidor
    heartbeat_interval: int | None = None
    server_current_time: str | None = None
    time_offset: float = 0.0
    
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

    # Objeto de sincronização para controle de concorrência em programas com múltiplas threads
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
            if f.name in ("_lock", "_allow_write"):
                continue
                
            val = getattr(default_instance, f.name)
            setattr(self, f.name, val)
            
    
    @locked
    def initialize_connectors(self, qty: int):
        """
        Inicializa a lista de conectores com estado padrão (Available, NoError).
        Deve ser chamado após a leitura da configuração e antes do primeiro StatusNotification.
        Os IDs dos conectores serão de 1 a qty.
        """
        self.connectors.clear()
        self.connectors_qty = qty
        for i in range(1, qty + 1):
            self.connectors.append(ConnectorState(connector_id=i))

    @locked
    def update_connector_status(
        self,
        connector_id: int,
        status: enums.ChargePointStatus,
        error_code: enums.ChargePointErrorCode = enums.ChargePointErrorCode.no_error,
        info: str | None = None
    ):
        """
        Atualiza o estado de um conector específico.
        Se o conector não existir, levanta ValueError.
        """
        for conn in self.connectors:
            if conn.connector_id == connector_id:
                conn.status = status
                conn.error_code = error_code
                conn.info = info
                conn.timestamp = self.get_current_time()
                return
        raise ValueError(f"Connector {connector_id} não encontrado")
        
            
    @locked
    def update_time_from_server(self, server_time_iso: str):
        """
        Método que garante a sincronicidade entre o relógio do servidor e o relógio virtual do cliente ocpp
        """
        server_time = datetime.fromisoformat(server_time_iso.replace('Z', '+00:00'))
        local_time = datetime.now(timezone.utc)
        self.time_offset = (server_time - local_time).total_seconds()
        self.server_current_time = server_time_iso
    
    def get_current_time(self) -> datetime:
        """Retorna a hora atual ajustada pelo offset (se desejado)."""
        ts = datetime.now(timezone.utc) + timedelta(seconds=self.time_offset)
        iso_ts = ts.isoformat(timespec='milliseconds').replace("+00:00", "Z")

        return iso_ts


# Criamos uma única instância global deste estado
state = ChargePointState()