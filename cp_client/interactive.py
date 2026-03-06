# cp_client/interactive.py
import asyncio
import shlex
import sys
from typing import Dict, Optional
import logging

from scenarios.base import Scenario
from scenarios.min_cycle import MinCycleScenario
from .base import setup_logger

logger = setup_logger("interactive")  # <-- agora usa setup_logger

class InteractiveHandler:
    """
    Handler que permite ao usuário digitar comandos para executar transações
    enquanto o Charge Point mantém a conexão ativa em background.
    """

    def __init__(self):
        self.running = True
        self.cp: Optional['ChargePoint'] = None   # Será atualizado pela tarefa de conexão
        self.transaction_counter = 0
        self.command_queue = None
        self.input_task = None

        # Registro de cenários disponíveis
        self.scenarios: Dict[str, Scenario] = {
            "min_cycle": MinCycleScenario(),
        }

    async def handle_commands(self):
        """Loop principal que recebe comandos do usuário de forma assíncrona."""
        self.command_queue = asyncio.Queue()
        self._print_welcome()

        loop = asyncio.get_running_loop()

        # Inicia a tarefa de leitura de input
        self.input_task = asyncio.create_task(self._input_reader())

        # Loop principal: aguarda comandos da fila
        try:
            while self.running:
                try:
                    command = await asyncio.wait_for(self.command_queue.get(), timeout=0.5)

                    if command is None:  # Comando de encerramento
                        self.running = False
                        break

                    if command:
                        await self._process_command(command)

                    # Após processar o comando, imprime o prompt novamente
                    if self.running:
                        print("\nDigite um comando: ", end='', flush=True)

                except asyncio.TimeoutError:
                    continue

        except asyncio.CancelledError:
            self.running = False
        finally:
            await self._cleanup()

    async def _input_reader(self):
        """Lê input do usuário de forma assíncrona."""
        try:
            # Primeiro prompt
            print("\nDigite um comando: ", end='', flush=True)

            while self.running:
                try:
                    loop = asyncio.get_running_loop()
                    line = await loop.run_in_executor(None, sys.stdin.readline)

                    if not line:  # EOF
                        await self.command_queue.put(None)
                        break

                    line = line.strip()
                    if line:
                        await self.command_queue.put(line)
                    else:
                        print("\nDigite um comando: ", end='', flush=True)

                except Exception as e:
                    logger.error(f"Erro na leitura de input: {e}")
                    await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Erro no _input_reader: {e}")

    def _print_welcome(self):
        """Exibe mensagem de boas-vindas."""
        print("\n" + "="*65)
        print("Sistema de Controle do Posto de Recarga - OCPP 1.6")
        print("="*65)
        print("Comandos disponíveis:")

        for name, scenario in self.scenarios.items():
            print(f"  {name:<15} - {self._get_scenario_description(name)}")

        print("  status               - Verifica status da conexão")
        print("  help                 - Mostra esta ajuda")
        print("  quit                 - Encerra o programa")
        print("="*65)

    def _get_scenario_description(self, scenario_name: str) -> str:
        """Retorna descrição do cenário."""
        descriptions = {
            "min_cycle": "Authorize → Start → 2xMeter → Stop \n                     params:  id_tag (default: 'CARD123')",
        }
        return descriptions.get(scenario_name, "")

    async def _process_command(self, command_line: str):
        """Processa uma linha de comando."""
        if not command_line:
            return

        try:
            parts = shlex.split(command_line)
            command = parts[0].lower()
            args = parts[1:]

            # Comandos do sistema
            if command in ['quit', 'exit']:
                await self._shutdown()

            elif command == 'help':
                self._print_welcome()

            elif command == 'status':
                await self._show_status()

            # Comandos de cenário
            elif command in self.scenarios:
                await self._execute_scenario(command, args)

            else:
                print(f"Comando desconhecido: {command}")
                print("Digite 'help' para ver os comandos disponíveis.")

        except Exception as e:
            logger.error(f"Erro ao processar comando '{command_line}': {e}")
            print(f"Erro ao processar comando: {e}")

    async def _execute_scenario(self, scenario_name: str, args: list):
        """
        Executa um cenário específico.

        Args:
            scenario_name: Nome do cenário a executar
            args: Argumentos para o cenário
        """
        # Verifica se o ChargePoint está disponível
        if self.cp is None:
            print("Posto não está conectado ao servidor. Aguarde reconexão.")
            return
        if not self.cp.registered:
            print("Posto não está registrado (BootNotification pendente).")
            return

        self.transaction_counter += 1
        scenario = self.scenarios[scenario_name]

        # Prepara kwargs baseado no cenário
        kwargs = {}
        if args and scenario_name == "min_cycle":
            kwargs['id_tag'] = args[0]  # pode ser string

        print(f"\n>     Executando cenário '{scenario_name}'")
        if kwargs:
            print(f"   Parâmetros: {kwargs}")

        try:
            success = await scenario.execute(self.cp, **kwargs)

            if success:
                print(f"-   Transação #{self.transaction_counter} concluída com sucesso!")
            else:
                print(f"-   Transação #{self.transaction_counter} falhou.")

        except Exception as e:
            logger.error(f" Erro na execução do cenário: {e}", exc_info=True)
            print(f" Erro durante execução: {e}")

    async def _show_status(self):
        """Mostra status atual do sistema."""
        print(f"\nStatus do Sistema:")
        if self.cp:
            print(f"  Station ID: {self.cp.station_id}")
            print(f"  Connector ID: {self.cp.connector_id}")
            print(f"  Registrado: {'OK' if self.cp.registered else 'X'}")
            print(f"  Transação ativa: {self.cp._transaction_id if self.cp._transaction_id else 'Nenhuma'}")
        else:
            print("!!! Posto desconectado do servidor !!!")

        print(f"  Total transações: {self.transaction_counter}")
        print(f"\n  Cenários disponíveis:")
        for name in self.scenarios.keys():
            print(f"    • {name}")

    async def _shutdown(self):
        """Método auxiliar para desligamento limpo."""
        print("\nEncerrando programa...")
        self.running = False
        if self.command_queue:
            await self.command_queue.put(None)

    async def _cleanup(self):
        """Limpeza final dos recursos."""
        print("\nEncerrando handler de comandos...")

        # Cancelar tarefa de input se estiver rodando
        if self.input_task and not self.input_task.done():
            self.input_task.cancel()
            try:
                await self.input_task
            except asyncio.CancelledError:
                pass

        print("Handler de comandos encerrado.")