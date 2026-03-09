# cp_client/client.py
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable

import websockets
from ocpp.v16 import ChargePoint as BaseChargePoint
from ocpp.v16 import call
from ocpp.v16.enums import RegistrationStatus, AuthorizationStatus

from config.settings import settings
from .base import setup_logger

logger = setup_logger("cp_client")

class ChargePoint(BaseChargePoint):
    def __init__(self, station_id: str, connection, response_timeout=30):
        super().__init__(station_id, connection, response_timeout)
        self.station_id = station_id
        self.connector_id = settings.connector_id
        self.registered = False
        self._transaction_id: Optional[int] = None
        self._stop_requested = False

    async def start(self):
        """Sobrescreve start para iniciar o loop de mensagens."""
        await super().start()

    async def send_boot_notification(self) -> bool:
        """Envia BootNotification e aguarda aceitação."""
        if self.registered:
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

            if response.status == RegistrationStatus.accepted:
                logger.info("BootNotification aceito", extra={"station_id": self.station_id})
                self.registered = True
                return True
            else:
                logger.warning(f"BootNotification rejeitado: {response.status}",
                               extra={"station_id": self.station_id})
                              
                return False
                
        except Exception as e:
            logger.error(f"Erro no BootNotification: {e}", extra={"station_id": self.station_id})
            return False
            

    async def authorize(self, id_tag: str) -> bool:
        request = call.Authorize(id_tag=id_tag)
        try:
            response = await self.call(request)
            if response.id_tag_info.get("status") == AuthorizationStatus.accepted:
                logger.info(f"Authorize aceito para idTag {id_tag}", extra={"station_id": self.station_id})
                return True
            else:
                logger.warning(f"Authorize rejeitado: {response.id_tag_info}", extra={"station_id": self.station_id})
                return False
        except Exception as e:
            logger.error(f"Erro durante Authorize para idTag {id_tag}: {e}", extra={"station_id": self.station_id})
            return False

    async def start_transaction(self, id_tag: str, meter_start: int, timestamp: datetime) -> Optional[int]:
        request = call.StartTransaction(
            connector_id=self.connector_id,
            id_tag=id_tag,
            meter_start=meter_start,
            timestamp=timestamp.isoformat()
        )
        try:
            response = await self.call(request)
            if response.id_tag_info.get("status") == AuthorizationStatus.accepted:
                transaction_id = response.transaction_id
                self._transaction_id = transaction_id
                logger.info(f"Transacao iniciada", extra={
                    "station_id": self.station_id,
                    "connector_id": self.connector_id,
                    "transaction_id": transaction_id,
                    "id_tag": id_tag
                })
                return transaction_id
            else:
                logger.warning(f"Falha ao iniciar transacao: {response.id_tag_info}", extra={"station_id": self.station_id})
                return None
        except Exception as e:
            logger.error(f"Erro no StartTransaction: {e}", extra={"station_id": self.station_id})
            return None

    async def send_meter_values(self, transaction_id: int, meter_value: int, timestamp: datetime):
        meter_value_entry = {
            "timestamp": timestamp.isoformat(),
            "sampledValue": [{"value": str(meter_value), "measurand": "Energy.Active.Import.Register"}]
        }
        request = call.MeterValues(
            connector_id=self.connector_id,
            transaction_id=transaction_id,
            meter_value=[meter_value_entry]
        )
        try:
            response = await self.call(request)
            logger.info(f"MeterValues enviado: {meter_value} Wh", extra={
                "station_id": self.station_id,
                "transaction_id": transaction_id,
                "meter_value": meter_value
            })
            return response
        except Exception as e:
            logger.error(f"Erro no MeterValues: {e}", extra={"station_id": self.station_id, "transaction_id": transaction_id})

    async def stop_transaction(self, transaction_id: int, meter_stop: int, timestamp: datetime, id_tag: Optional[str] = None):
        request = call.StopTransaction(
            transaction_id=transaction_id,
            meter_stop=meter_stop,
            timestamp=timestamp.isoformat(),
            id_tag=id_tag
        )
        try:
            response = await self.call(request)
            logger.info("Transacao encerrada", extra={
                "station_id": self.station_id,
                "transaction_id": transaction_id,
                "meter_stop": meter_stop
            })
            self._transaction_id = None
            return response
        except Exception as e:
            logger.error(f"Erro no StopTransaction: {e}", extra={"station_id": self.station_id, "transaction_id": transaction_id})

    async def send_heartbeat(self):
        """Envia Heartbeat periodicamente."""
        while not self._stop_requested:
            await asyncio.sleep(settings.heartbeat_interval)
            try:
                request = call.Heartbeat()
                response = await self.call(request)
                logger.debug("Heartbeat enviado", extra={"station_id": self.station_id})
            except Exception as e:
                logger.warning(f"Falha no heartbeat: {e}", extra={"station_id": self.station_id})
                break


async def run_charge_point_with_reconnect(
    on_connect: Optional[Callable[[ChargePoint], Awaitable[None]]] = None,
    on_disconnect: Optional[Callable[[], Awaitable[None]]] = None
):
    """
    Gerencia a conexão persistente do Charge Point com reconexão automática.
    Notifica via callbacks quando um novo ChargePoint é conectado ou quando a conexão é perdida.
    """
    retries = 0
    while retries < settings.max_retries:
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
                timeout=settings.connection_timeout
            )

            async with ws:
                cp = ChargePoint(settings.station_id, ws, response_timeout=settings.response_timeout)

                # Inicia o loop de recebimento de mensagens em background
                start_task = asyncio.create_task(cp.start())

                try:
                    # Envia BootNotification e aguarda aceitação
                    if not await cp.send_boot_notification():
                        logger.error("BootNotification nao aceito, desconectando...")
                        start_task.cancel()
                        try:
                            await start_task
                        except asyncio.CancelledError:
                            pass
                        await ws.close()
                        continue  # Tenta reconectar

                    # Notifica conexão estabelecida
                    if on_connect:
                        await on_connect(cp)

                    # Aguarda até que a tarefa start termine (conexão caiu)
                    await start_task

                except Exception as e:
                    logger.error(f"Erro durante a operacao: {e}")
                    start_task.cancel()
                    try:
                        await start_task
                    except asyncio.CancelledError:
                        pass
                    raise  # Propaga para o bloco de exceções externo

                # Se saiu do start, a conexão foi encerrada normalmente
                logger.info("Conexao encerrada normalmente.")
                break

        except (websockets.ConnectionClosed, ConnectionRefusedError, OSError, asyncio.TimeoutError) as e:
            retries += 1
            delay = settings.base_delay * 1
            logger.warning(f"Conexão perdida ou falhou. Tentativa {retries}/{settings.max_retries}. "
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