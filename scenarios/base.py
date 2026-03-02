# scenarios/base.py
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict

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