# scenarios/min_cycle.py
import asyncio
from datetime import datetime, timezone

from cp_client.client import ChargePoint
from config.settings import settings
from .base import Scenario

class MinCycleScenario(Scenario):
    """
    Cenário de ciclo mínimo:
    Authorize -> StartTransaction -> (2x MeterValues) -> StopTransaction
    """
    
    def __init__(self):
        super().__init__("min_cycle")

    async def execute(self, cp: ChargePoint, **kwargs) -> bool:
        # Obtém o id_tag dos argumentos nomeados (com fallback para settings)
        id_tag = kwargs.get('id_tag', settings.id_tag)

        if not cp.registered:
            return False

        # 1. Authorize
        auth_ok = await cp.authorize(id_tag)
        if not auth_ok:
            logger.error(f"Authorization failed for tag {id_tag}")
            return False

        # 2. StartTransaction
        now = datetime.now(timezone.utc)
        transaction_id = await cp.start_transaction(id_tag, meter_start=1000, timestamp=now)
        if not transaction_id:
            return False

        # 3. MeterValues durante a transação
        await asyncio.sleep(2)
        now2 = datetime.now(timezone.utc)
        await cp.send_meter_values(transaction_id, meter_value=1010, timestamp=now2)

        await asyncio.sleep(2)
        now3 = datetime.now(timezone.utc)
        await cp.send_meter_values(transaction_id, meter_value=1020, timestamp=now3)

        # 4. StopTransaction
        now4 = datetime.now(timezone.utc)
        await cp.stop_transaction(transaction_id, meter_stop=1030, timestamp=now4, id_tag=id_tag)

        return True