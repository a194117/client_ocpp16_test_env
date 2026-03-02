# main.py
import asyncio
import signal
import logging
from cp_client.client import run_charge_point_with_reconnect
from cp_client.interactive import InteractiveHandler
from cp_client.base import setup_logger

async def main():
    """Função principal que inicia o sistema interativo."""
    setup_logger("cp_client")
    setup_logger("interactive")

    # Cria o handler interativo
    handler = InteractiveHandler()

    # Configura tratamento de sinais para encerramento gracioso
    loop = asyncio.get_running_loop()

    def signal_handler():
        handler.running = False

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Callbacks para atualizar o handler com o ChargePoint atual
    async def on_connect(cp):
        handler.cp = cp

    async def on_disconnect():
        handler.cp = None

    # Inicia a tarefa de conexão (em background)
    connection_task = asyncio.create_task(
        run_charge_point_with_reconnect(
            on_connect=on_connect,
            on_disconnect=on_disconnect
        )
    )

    # Inicia a tarefa interativa
    interactive_task = asyncio.create_task(handler.handle_commands())

    # Aguarda qualquer uma das tarefas terminar (ou ser cancelada)
    done, pending = await asyncio.wait(
        [connection_task, interactive_task],
        return_when=asyncio.FIRST_COMPLETED
    )

    # Cancela a tarefa que ainda estiver rodando
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n Programa encerrado pelo usuário.")