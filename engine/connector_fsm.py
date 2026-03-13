from cp_client.client import ChargePoint
from store.state import state

from ocpp.v16.enums import ChargePointStatus, ChargePointErrorCode

import logging
logger = logging.getLogger("connectorFSM")

class ConnectorStateMachine:
    #def __init__(self):
        # Construtor: inicializa os atributos
        #self.atributo = valor
    
    @staticmethod
    async def validate_transition(cp: ChargePoint, connectorId: int, nextState: ChargePointStatus) -> bool:
        """
        Método responsável por estruturar a maquina de estados que garante a correta dinâmica de funcionamento dos conectores. Esta maquina de estados foi contruida com base na 'Matriz de Transição de Status do Conector' contida na sessão '4.9. Status Notification' da documentação oficial do OCPP v1.6
        """
        isValid = False
        
        if connectorId == 0 and (nextState != ChargePointStatus.available or ChargePointStatus.unavailable or ChargePointStatus.faulted):
            return False
        
        try:
            prevState = state.get_connector_state(connectorId).get("status")
        except ValueError as e :
            logger.error(f"Erro durante transicao de estado do conector: {e}")
            return False
        
        match prevState:
            case ChargePointStatus.available:
                isValid = (nextState == ChargePointStatus.preparing or ChargePointStatus.charging or ChargePointStatus.suspended_evse or ChargePointStatus.suspended_ev or ChargePointStatus.reserved or ChargePointStatus.unavailable or ChargePointStatus.faulted)
                
            case ChargePointStatus.preparing:
                isValid = (nextState == ChargePointStatus.available or ChargePointStatus.charging or ChargePointStatus.suspended_evse or ChargePointStatus.suspended_ev or ChargePointStatus.finishing or ChargePointStatus.faulted)
                
            case ChargePointStatus.charging:
                isValid = (nextState == ChargePointStatus.available or ChargePointStatus.suspended_evse or ChargePointStatus.suspended_ev or ChargePointStatus.finishing or ChargePointStatus.unavailable or ChargePointStatus.faulted)
                
            case ChargePointStatus.suspended_ev:
                isValid = (nextState == ChargePointStatus.available or ChargePointStatus.charging or ChargePointStatus.suspended_evse or ChargePointStatus.finishing or ChargePointStatus.unavailable or ChargePointStatus.faulted)
                
            case ChargePointStatus.suspended_evse:
                isValid = (nextState == ChargePointStatus.available or ChargePointStatus.charging or ChargePointStatus.suspended_ev or ChargePointStatus.finishing or ChargePointStatus.unavailable or ChargePointStatus.faulted)
                
            case ChargePointStatus.finishing:
                isValid = (nextState == ChargePointStatus.available or ChargePointStatus.preparing or ChargePointStatus.unavailable or ChargePointStatus.faulted)
                
            case ChargePointStatus.reserved:
                isValid = (nextState == ChargePointStatus.available or ChargePointStatus.preparing or ChargePointStatus.unavailable or ChargePointStatus.faulted)
                
            case ChargePointStatus.unavailable:
                isValid = (nextState == ChargePointStatus.available or ChargePointStatus.preparing or ChargePointStatus.charging or ChargePointStatus.suspended_evse or ChargePointStatus.suspended_ev or ChargePointStatus.faulted)
                
            case ChargePointStatus.faulted:
                isValid = (nextState == ChargePointStatus.available or ChargePointStatus.preparing or ChargePointStatus.charging or ChargePointStatus.suspended_evse or ChargePointStatus.suspended_ev or ChargePointStatus.finishing or ChargePointStatus.reserved or ChargePointStatus.unavailable)
                
        if isValid:
            try:
                await cp.send_status_notification(
                    connector_id=connectorId, 
                    status=nextState,
                    error_code=ChargePointErrorCode.no_error
                )
            except Exception as e:
                return False
                
            state.update_connector_status(
                connector_id=connectorId, 
                status=nextState,
                error_code=ChargePointErrorCode.no_error
            )
            logger.info(f"Status do conector {connectorId} modificado internamente para {nextState}")
        else:
            logger.error(f"Erro durante transicao de estado do conector: Não é possível modificar o Status do conector {connectorId} de {prevState} para {nextState}")
        
        return isValid