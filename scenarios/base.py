# scenarios/base.py
import asyncio
import math
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict

from ocpp.v16.enums import Measurand

from config.settings import settings
from store.meters import meters
from store.conf_keys import configuration_keys

import logging

logger = logging.getLogger("scenarios")

class Scenario(ABC):
    """
    Classe base abstrata para todos os cenários de transação.
    Cada cenário deve implementar o método execute().
    """
    
    def __init__(self, name: str):
        self.name = name
        self.transaction_id: Optional[int] = None


    @abstractmethod
    async def execute(self, cp, **kwargs) -> bool:
        """
        Executa o cenário de transação.
        
        Args:
            cp: Instância do ChargePoint
            **kwargs: Argumentos específicos do cenário
            
        Returns:
            bool: True se a transação foi concluída com sucesso
        """
        pass
        
    def get_context(self) -> Dict[str, Any]:
        """Retorna o contexto atual para logging."""
        return {
            "scenario": self.name,
            "transaction_id": self.transaction_id,
        }
        
    async def perform_recharge(self, send_meter_values, recharge_value, connector_id, transaction_id):
        """ 
        Simula o processo de Recarga realizado pelo Eletroposto 
        
        A partir dos valores de corrente tensão contidos nos medidores
        E do valor do intervalode tempo de amostragem durante a transação
        Atualiza valor dos registradores de mediação e
        Realiza um loop que envia meter_values periodicos ao servidor
        """
        
        
        sampling_time=configuration_keys.get("MeterValueSampleInterval")
        
        inst_volt=float(meters.get_value(connector_id, Measurand.voltage))
        inst_curr=float(meters.get_value(connector_id, Measurand.current_import))
        
        inst_pot=inst_volt*inst_curr
        meters.set_value(connector_id, Measurand.power_active_import ,inst_pot)
        
        operating_time=(recharge_value*1000/inst_pot)*360
        
        frac, n = math.modf(operating_time/sampling_time)
        
        input_pot = inst_pot * sampling_time / 360
        
        for i in range(math.floor(n), -1, -1):
            
            await asyncio.sleep(sampling_time/settings.time_scale)
            
            if i == 0:
                meters.update_active_import_register(connector_id, frac * input_pot)
            else: 
                meters.update_active_import_register(connector_id, input_pot)
            
            await send_meter_values(connector_id, transaction_id)