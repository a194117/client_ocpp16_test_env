# cp_client/client.py
import asyncio
import logging
from datetime import timezone
from typing import Optional, Callable, Awaitable

import websockets
from ocpp.v16 import ChargePoint as BaseChargePoint
from ocpp.v16 import call
from ocpp.v16.enums import RegistrationStatus, AuthorizationStatus, ChargePointStatus, ChargePointErrorCode, ReadingContext, Measurand, Reason

from store.state import state
from store.conf_keys import configuration_keys
from store.meters import meters
from config.settings import settings
from .base import setup_logger
from .context import set_transaction_id

logger = setup_logger("cp_client")

class ChargePoint(BaseChargePoint):
    def __init__(self, station_id: str, connection, response_timeout=30):
        super().__init__(station_id, connection, response_timeout)
        self.station_id = station_id
        self._stop_requested = False
        self.connector_id = 1

    async def start(self):
        """Sobrescreve start para iniciar o loop de mensagens."""
        await super().start()

    async def send_boot_notification(self) -> bool:
        """Envia BootNotification e aguarda aceitação."""
        if state.registration:
            logger.debug("BootNotification ja foi aceito anteriormente")
            return True
            
        boot_kwargs = {
            "charge_point_model": settings.charge_point_model,
            "charge_point_vendor": settings.charge_point_vendor,
        }    
        if settings.charge_box_serial_number:
            boot_kwargs["charge_box_serial_number"] = settings.charge_box_serial_number
        if settings.charge_point_serial_number:
            boot_kwargs["charge_point_serial_number"] = settings.charge_point_serial_number
        if settings.firmware_version:
            boot_kwargs["firmware_version"] = settings.firmware_version
        if settings.iccid:
            boot_kwargs["iccid"] = settings.iccid
        if settings.imsi:
            boot_kwargs["imsi"] = settings.imsi
        if settings.meter_serial_number:
            boot_kwargs["meter_serial_number"] = settings.meter_serial_number
        if settings.meter_type:
            boot_kwargs["meter_type"] = settings.meter_type

        request = call.BootNotification(**boot_kwargs)
        
        try:
            response = await self.call(request)
            logger.info(f"SendBootNotification.conf recebido com 'status': '{response.status}'")

            try:
                state.update(registration=response.status)
                if response.interval:
                    configuration_keys.set("HeartbeatInterval", response.interval)
                
                if state.registration == RegistrationStatus.rejected:
                    return False
                else:          
                    state.update_time_from_server(response.current_time)
                    return True
            
            except ValueError:
                raise Exception(f"'{response.status}' não é um estado de registro válido.")
                               
        except Exception as e:
            logger.error(f"Erro no BootNotification.req: {e}")
            return False
            
    async def send_status_notification(self, connector_id: int, status: ChargePointStatus, error_code: ChargePointErrorCode, timestamp:  str | None = None, info:  str | None = None, vendor_id:  str | None = None, vendor_error_code:  str | None = None ):
        """
        Envia uma mensagem StatusNotification para um conector específico.
        """

        status_kwargs = {
            "connector_id": connector_id, 
            "status": status, 
            "error_code": error_code,
        }    
        if timestamp:
            status_kwargs["timestamp"] = timestamp
        if info:
            status_kwargs["info"] = info
        if vendor_id:
            status_kwargs["vendor_id"] = vendor_id
        if vendor_error_code:
            status_kwargs["vendor_error_code"] = vendor_error_code

        request = call.StatusNotification(**status_kwargs)

        try:
            response = await self.call(request)
            logger.info(f"StatusNotification.req enviado com 'status': '{status.value}'")
        except Exception as e: 
            logger.error(f"Falha ao enviar StatusNotification.req: {e}")
            raise 


    async def authorize(self, id_tag: str) -> bool:
        if state.registration == RegistrationStatus.accepted:
            request = call.Authorize(id_tag=id_tag)
            try:
                response = await self.call(request)
                if response.id_tag_info.get("status") == AuthorizationStatus.accepted:
                    logger.info(f"Authorize.conf 'status': {response.id_tag_info.get('status')}, 'idTag': '{id_tag}'")
                    return True
                else:
                    logger.warning(f"Authorize.conf 'status': {response.id_tag_info.get('status')}, 'idTag': '{id_tag}'")
                    return False
            except Exception as e:
                logger.error(f"Erro durante Authorize.req 'idTag': '{id_tag}'. Erro: {e}")
                return False
        else : 
            logger.warning(f"O Registro do CP não foi aceito, Authorize.req não pode ser enviado")
            return False

    async def start_transaction(self, connector_id: int, id_tag: str, reservation_id: Optional[int] = 0) -> Optional[int]:
        if state.registration == RegistrationStatus.accepted:
            
            timestamp = state.get_current_time()
            
            sampled_values = meters.get_meter_value(
                connector_id=connector_id,
                measurands=None,
            )
            
            meter_start=int(float(sampled_values[0].get("value")))
            
            start_kwargs = {
                "connector_id":self.connector_id,
                "id_tag":id_tag,
                "meter_start":meter_start,
                "timestamp":timestamp,
            }
            if reservation_id:
                start_kwargs["reservation_id"]=reservation_id
            
            request = call.StartTransaction(**start_kwargs)
            
            try:
                response = await self.call(request)
                set_transaction_id(response.transaction_id)
                if response.id_tag_info.get("status") == AuthorizationStatus.accepted:
                    transaction_id = response.transaction_id
                    self._transaction_id = transaction_id
                    logger.info(f"StartTransaction.conf 'status': {response.id_tag_info.get('status')}, 'meter_start' : {meter_start}")
                    return transaction_id
                else:
                    logger.warning(f"StartTransaction.conf 'status': {response.id_tag_info.get('status')}, 'meter_start' : {meter_start}")
                    set_transaction_id(None)
                    return None
            except Exception as e:
                logger.error(f"Erro no StartTransaction.req: {e}")
                set_transaction_id(None)
                return None
        else : 
            logger.warning(f"O Registro do CP não foi aceito, transacao nao pode ser iniciada:")
            return None

    async def send_transaction_meter_values(self, connector_id: int, transaction_id: int):
        timestamp = state.get_current_time()
                        
        sampled_values = meters.get_meter_value(
            connector_id=connector_id,
            measurands=configuration_keys.get("MeterValuesSampledData"),
            context=ReadingContext.sample_periodic
        )

        # Prepara o entry para o MeterValues
        meter_value_entry = {
            "timestamp": timestamp,
            "sampledValue": sampled_values
        }
                        
        request = call.MeterValues(
            connector_id=connector_id,
            transaction_id=transaction_id,
            meter_value=[meter_value_entry]
        )
        
        try:  
            response = await self.call(request)
            logger.info(f"MeterValues.req enviado 'context':{ReadingContext.sample_periodic}")
        except Exception as e:
            logger.error(f"Falha ao enviar MeterValues.req 'context':{ReadingContext.sample_periodic}: {e}") 


    async def stop_transaction(self, connector_id: int, transaction_id: int, id_tag: Optional[str] = None, reason: Optional[str] = None, transaction_data: Optional[bool] = None):
        
        timestamp = state.get_current_time()
        
        sampled_values = meters.get_meter_value(
            connector_id=connector_id,
            measurands=None,
        )
        
        meter_stop=int(float(sampled_values[0].get("value")))
    
        stop_kwargs = {
            "transaction_id":transaction_id,
            "meter_stop":meter_stop,
            "timestamp":timestamp,
        }
        if id_tag:
            stop_kwargs["id_tag"]=id_tag
        if reason:
            stop_kwargs["reason"]=reason
        else:
            stop_kwargs["reason"]=Reason.local
        if transaction_data:
            sampled_values = meters.get_meter_value(
                connector_id=connector_id,
                measurands=configuration_keys.get("MeterValuesSampledData"),
                context=ReadingContext.sample_periodic
            )
            meter_value_entry = {
                "timestamp": timestamp,
                "sampledValue": sampled_values
            }
            stop_kwargs["transaction_data"]=[meter_value_entry]
    
        request = call.StopTransaction(**stop_kwargs)

        try:
            response = await self.call(request)
            logger.info(f"StopTransaction.req enviado 'meter_stop': {meter_stop}, 'id_tad': {id_tag}, 'reason': {reason}")
            self._transaction_id = None
            return response
        except Exception as e:
            logger.error(f"Erro no StopTransaction.req: {e}")

    async def send_heartbeat(self):
        """Envia Heartbeat periodicamente, usando o intervalo definido pelo servidor."""
        try:
            while not self._stop_requested:
                """Utiliza Time Scale para adequar ao tempo de simulação."""
                await asyncio.sleep(configuration_keys.get("HeartbeatInterval")/settings.time_scale)
                try:
                    request = call.Heartbeat()
                    response = await self.call(request)
                    state.update_time_from_server(response.current_time)
                    logger.debug("Heartbeat.req enviado")
                except Exception as e:
                    logger.warning(f"Falha no Heartbeat.req: {e}")
                    break   # Sai do loop se houver erro (a tarefa será cancelada externamente)
        except asyncio.CancelledError:
            logger.info("Tarefa de heartbeat cancelada")
            self._stop_requested = True
            raise   # Re-lança para que a tarefa seja marcada como cancelada
            
    async def send_periodic_meter_values(self):
        """Envia MeterValue periodicamente, usando o intervalo definido pelo Usuário."""
        try:
            while not self._stop_requested:
                """Utiliza Time Scale para adequar ao tempo de simulação."""
                await asyncio.sleep(configuration_keys.get("ClockAlignedDataInterval")/settings.time_scale)
                for connector in state.connectors:
                    try:
                        timestamp = state.get_current_time()
                        
                        sampled_values = meters.get_meter_value(
                            connector_id=connector.connector_id,
                            measurands=configuration_keys.get("MeterValuesAlignedData"),
                            context=ReadingContext.sample_clock 
                        )

                        # Prepara o entry para o MeterValues
                        meter_value_entry = {
                            "timestamp": timestamp,
                            "sampledValue": sampled_values
                        }
                        
                        request = call.MeterValues(
                            connector_id=connector.connector_id,
                            transaction_id=None,
                            meter_value=[meter_value_entry]
                        )
                      
                        response = await self.call(request)
                        logger.info(f"MeterValues.req enviado 'context':{ReadingContext.sample_clock}")
                    except Exception as e:
                        logger.error(f"Falha ao enviar MeterValues.req 'context':{ReadingContext.sample_periodic}: {e}")
                        continue  
                        
        except asyncio.CancelledError:
            logger.info("Tarefa de PeriodicMeterValues cancelada")
            self._stop_requested = True
            raise   # Re-lança para que a tarefa seja marcada como cancelada


async def run_charge_point_with_reconnect(
    on_connect: Optional[Callable[[ChargePoint], Awaitable[None]]] = None,
    on_disconnect: Optional[Callable[[], Awaitable[None]]] = None
):
    """
    Gerencia a conexão persistente do Charge Point com reconexão automática.
    Notifica via callbacks quando um novo ChargePoint é conectado ou quando a conexão é perdida.
    """
    retries = 0
    while retries < configuration_keys.get("ResetRetries"):
        try:
            ws_url = f"{settings.ws_url}{settings.station_id}"
            logger.info(f"Tentando conectar a {ws_url}")

            ws = await asyncio.wait_for(
                websockets.connect(
                    ws_url,
                    subprotocols=["ocpp1.6"],
                    ping_interval=20,
                    ping_timeout=10
                ),
                timeout=configuration_keys.get("ConnectionTimeOut")
            )

            async with ws:
                cp = ChargePoint(settings.station_id, ws, response_timeout=settings.response_timeout)

                # Inicia o loop de recebimento de mensagens em background
                start_task = asyncio.create_task(cp.start())
                heartbeat_task = None
                periodic_meter_values_task = None

                try:
                    # Envia BootNotification e aguarda aceitação
                    if not await cp.send_boot_notification():
                        logger.error("BootNotification nao aceito, desconectando...")
                        start_task.cancel()
                        try:
                            await start_task
                        except asyncio.CancelledError:
                            pass
                        continue  # Tenta reconectar
                        
                        
                    # Envia StatusNotification para o CP
                    await cp.send_status_notification(
                        connector_id=0, 
                        status=state.status,
                        error_code=state.error_code
                    )
                    
                    # Inicializa os conectores na store global
                    state.initialize_connectors(configuration_keys.get("NumberOfConnectors")) 

                    # Envia StatusNotification para cada conector
                    for connector in state.connectors:
                        await cp.send_status_notification(
                            connector_id=connector.connector_id,
                            status=connector.status,
                            error_code=connector.error_code,
                            info=connector.info
                        )

                    # Notifica conexão estabelecida
                    if on_connect:
                        await on_connect(cp)
                    
                    # --- Tarefa 2: heartbeat periódico (iniciado APÓS BootNotification) ---
                    heartbeat_task = asyncio.create_task(cp.send_heartbeat())
                    
                    # --- Tarefa 3: meter values periódicos ---
                    periodic_meter_values_task = asyncio.create_task(cp.send_periodic_meter_values())

                    # Aguarda a primeira tarefa finalizar (conexão perdida ou heartbeat falhou)
                    done, pending = await asyncio.wait(
                        [start_task, heartbeat_task, periodic_meter_values_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # Cancela a tarefa que ainda está pendente
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                    # Verifica se alguma das tarefas concluídas lançou exceção
                    for task in done:
                        exc = task.exception()
                        if exc and not isinstance(exc, asyncio.CancelledError):
                            logger.error(f"Tarefa finalizou com exceção: {exc}")
                            # Relança a exceção para que o loop externo trate como falha
                            raise exc
                            
                except asyncio.CancelledError:
                    logger.info("Cancelamento detectado, encerrando tarefas internas...")
                    for task in (start_task, heartbeat_task, periodic_meter_values_task):
                        if task and not task.done():
                            task.cancel()
                    await asyncio.gather(
                        *[t for t in (start_task, heartbeat_task, periodic_meter_values_task) if t],
                        return_exceptions=True
                    )
                    raise


                except Exception as e:
                    for task in (start_task, heartbeat_task, periodic_meter_values_task):
                        if task and not task.done():
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass
                    logger.error(f"Erro durante a operação: {e}")
                    raise

                # Se chegou aqui, a conexão foi encerrada voluntariamente (raro)
                logger.info("Conexão encerrada normalmente.")
                break

        except (websockets.ConnectionClosed, ConnectionRefusedError, OSError, asyncio.TimeoutError) as e:
            retries += 1
            delay = settings.base_delay * 1
            logger.warning(f"Conexão perdida ou falhou. Tentativa {retries}/{settings.reset_retries}. "
                           f"Reconectando em {delay:.1f}s. Erro: {e}")
            if on_disconnect:
                await on_disconnect()
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            logger.info("Tarefa de conexao cancelada.")
            if on_disconnect:
                await on_disconnect()
            break
        except Exception as e:
            logger.exception(f"Erro inesperado: {e}")
            if on_disconnect:
                await on_disconnect()
            break
    else:
        logger.error("Numero maximo de tentativas atingido. Encerrando.")
        if on_disconnect:
            await on_disconnect()