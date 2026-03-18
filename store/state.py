# store/state.py
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

from ocpp.v16 import enums
from ocpp.v16 import datatypes 

from .base import BaseLockedState, locked
    
@dataclass
class ConnectorState:
    """Estado de um conector individual."""
    connector_id: int
    status: enums.ChargePointStatus = enums.ChargePointStatus.available
    error_code: enums.ChargePointErrorCode = enums.ChargePointErrorCode.no_error
    info: str | None = None
    timestamp: datetime | None = None


@dataclass
class ChargePointState(BaseLockedState):
    """
    Estado global do Charge Point, incluindo status, configurações, transações.
    """
    def __init__(self):
        super().__init__()
        # Status básico do CP
        self.registration: enums.ChargePointStatus | None = None
        self.status: enums.ChargePointStatus = enums.ChargePointStatus.available
        self.error_code: enums.ChargePointErrorCode = enums.ChargePointErrorCode.no_error
        self.info: str | None = None
    
        # Conectores
        self.connectors_qty: int = 0
        self.connectors: List[ConnectorState] = []  
    
        # Relógio Interno para sincronização com o servidor
        self.server_current_time: str | None = None
        self.time_offset: float = 0.0
    
        # Lista de autorizações locais (local auth list)
        """       
        !!!! A IMPLEMENTAR !!!!
        
        self.local_auth_list: List[datatypes.AuthorizationData] = = []
        self.local_auth_list_version: int = 0
        """

        # Perfis de carregamento ativos (TxProfile, ChargePointMaxProfile, etc.)
        """       
        !!!! A IMPLEMENTAR !!!!
        self.charging_profiles: List[datatypes.ChargingProfile] = = []
        """

        # Transação atual (se houver)
        self.current_transaction_id: int | None = None
        self.current_connector_id: int | None = None
        self.id_tag_in_transaction: str | None = None
        self.current_transaction_power: float | None = None

        
        # Reservas ativas
        """
        !!!! A IMPLEMENTAR !!!!
        self.reservations: List[dict] = = []  # Você pode criar uma dataclass 
        """

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
    
    
    def get_connector_state(self, connector_id: int) -> dict | None:
        """
        Retorna um dicionario contendo as propriedades do ConnectorState com o ID fornecido, ou None se não existir.
        """
        for connector in self.connectors:
            if connector.connector_id == connector_id:
                return {
                    'connector_id': connector.connector_id,
                    'status': connector.status,
                    'error_code': connector.error_code,
                    'info': connector.info,
                    'timestamp': connector.timestamp,
                }
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