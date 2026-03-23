# scenarios/min_cycle.py
import asyncio

from engine.connector_fsm import ConnectorStateMachine as fsm
from cp_client.client import ChargePoint
from config.settings import settings
from store.state import state
from .base import Scenario

from ocpp.v16.enums import ChargePointStatus, ChargePointErrorCode

class MinCycleScenario(Scenario):
    """
    Cenário de ciclo mínimo:
    Authorize -> StartTransaction -> (2x MeterValues) -> StopTransaction
    """
    
    def __init__(self):
        super().__init__("min_cycle")

    async def execute(self, cp: ChargePoint, **kwargs) -> bool:
        # Obtém os argumentos id_tag & connector_id  (com fallback)
        recharge_value = kwargs.get('recharge_value', settings.recharge_value)
        id_tag = kwargs.get('id_tag', settings.id_tag)
        connector_id = kwargs.get('connector_id', 1)
        
        validated = await fsm.validate_transition(cp, connector_id, ChargePointStatus.preparing)
        if not validated:
            return False

        if not state.registration:
            return False

        # 1. Authorize
        auth_ok = await cp.authorize(id_tag)
        if not auth_ok:
            logger.error(f"Authorization failed for tag {id_tag}")
            await fsm.validate_transition(cp, connector_id, ChargePointStatus.available)
            return False
            
        validated = await fsm.validate_transition(cp, connector_id, ChargePointStatus.charging)
        if not validated:
            return False

        # 2. StartTransaction
        transaction_id = await cp.start_transaction(connector_id, id_tag)
        if not transaction_id:
            await fsm.validate_transition(cp, connector_id, ChargePointStatus.available)
            return False
            
        # 3. MeterValues durante a transação
        await self.perform_recharge(cp.send_transaction_meter_values, recharge_value, connector_id, transaction_id)

        # 4. StopTransaction
        await cp.stop_transaction(connector_id, transaction_id, id_tag=id_tag)
        
        
        validated = await fsm.validate_transition(cp, connector_id, ChargePointStatus.finishing)
        if not validated:
            return False
            
        validated = await fsm.validate_transition(cp, connector_id, ChargePointStatus.available)
        if not validated:
            return False

        return True