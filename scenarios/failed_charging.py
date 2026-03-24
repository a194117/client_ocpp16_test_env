# scenarios/failed_charging.py
import asyncio
import logging

from engine.connector_fsm import ConnectorStateMachine as fsm
from cp_client.client import ChargePoint
from cp_client.context import set_connector_id, set_transaction_id
from config.settings import settings
from store.state import state
from .base import Scenario, Parameter

from ocpp.v16.enums import ChargePointStatus, ChargePointErrorCode

logger = logging.getLogger("scenarios")

class FailedChargingScenario(Scenario):
    """
    Cenário de ciclo mínimo:
    Authorize -> StartTransaction -> (2x MeterValues) -> StopTransaction
    """
    
    _failed_charging_parameters = [
        Parameter("id_tag", default="CARD123", p_type="str", description="Tag do usuário"),
        Parameter("connector_id", default="1", p_type="int", description="ID do conector"),
    ]
    
    def __init__(self):
        super().__init__("failed_charging", self._failed_charging_parameters, True)

    async def execute(self, cp: ChargePoint, **kwargs) -> bool:
        # Obtém os argumentos id_tag & connector_id  (com fallback)
        recharge_value = kwargs.get('recharge_value', settings.recharge_value)
        id_tag = kwargs.get('id_tag', settings.id_tag)
        connector_id = kwargs.get('connector_id', 1)
        
        set_connector_id(connector_id)
        
        validated = await fsm.validate_transition(cp, connector_id, ChargePointStatus.preparing)
        if not validated:
            set_connector_id(None)
            return False

        if not state.registration:
            set_connector_id(None)
            return False

        # 1. Authorize
        auth_ok = await cp.authorize(id_tag)
        if not auth_ok:
            logger.error(f"Authorization failed for tag {id_tag}")
            await fsm.validate_transition(cp, connector_id, ChargePointStatus.available)
            set_connector_id(None)
            return False
            
        validated = await fsm.validate_transition(cp, connector_id, ChargePointStatus.charging)
        if not validated:
            logger.error(f"It is not possible to access the state {ChargePointStatus.charging}")
            await fsm.validate_transition(cp, connector_id, ChargePointStatus.available)
            set_connector_id(None)
            return False

        # 2. StartTransaction
        transaction_id = await cp.start_transaction(connector_id, id_tag)
        if not transaction_id:
            logger.error(f"It is not possible to start the transaction for tag {id_tag}")
            await fsm.validate_transition(cp, connector_id, ChargePointStatus.available)
            set_connector_id(None)
            set_transaction_id(None)
            return False
            
        # 3. MeterValues durante a transação
        set_transaction_id(transaction_id)
        stop_reason = await self.perform_recharge(cp.send_transaction_meter_values, recharge_value, connector_id, transaction_id)
        
        validated = await fsm.validate_transition(cp, connector_id, ChargePointStatus.faulted)
        if not validated:
            logger.error(f"It is not possible to access the state {ChargePointStatus.charging}")
            await fsm.validate_transition(cp, connector_id, ChargePointStatus.available)
            set_connector_id(None)
            set_transaction_id(None)
            return False

        # 4. StopTransaction
        await cp.stop_transaction(connector_id, transaction_id, id_tag=id_tag, reason=stop_reason)
        
        validated = await fsm.validate_transition(cp, connector_id, ChargePointStatus.available)
        if not validated:
            logger.error(f"It is not possible to access the state {ChargePointStatus.charging}")
            await fsm.validate_transition(cp, connector_id, ChargePointStatus.available)
            set_connector_id(None)
            set_transaction_id(None)
            return False

        set_connector_id(None)
        set_transaction_id(None)
        return True