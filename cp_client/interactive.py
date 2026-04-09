# cp_client/interactive.py
import asyncio
import shlex
import sys
from typing import Dict, Optional
import logging

from scenarios.base import Scenario
from scenarios.min_cycle import MinCycleScenario
from scenarios.failed_charging import FailedChargingScenario
from .base import setup_logger

from store.state import state

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

        # Registro de cenários disponíveis
        self.scenarios: Dict[str, Scenario] = {
            "min_cycle": MinCycleScenario(),
            "failed_charging": FailedChargingScenario(),
        }

    async def handle_commands(self):
        """Loop principal que recebe comandos do usuário de forma assíncrona."""
        self._print_welcome()

        loop = asyncio.get_running_loop()


        # Loop principal: aguarda comandos da fila
        try:
            while self.running:

                
                print("\nDigite um comando: ", end='', flush=True)
                command_line = await loop.run_in_executor(None, sys.stdin.readline)

                if not command_line:  # EOF
                    self.running = False
                    break

                command_line = command_line.strip()
                if command_line:
                    await self._process_command(command_line)    

        except asyncio.CancelledError:
            self.running = False
        except Exception as e:
            logger.error(f"Erro no loop de comandos: {e}", exc_info=True)
        finally:
            await self._cleanup()

    def _print_welcome(self):
        print("\n" + "="*70)
        print(" "*9+"Sistema de Controle do Posto de Recarga - OCPP 1.6")
        print("="*70)
        print("Comandos disponíveis:")

        for name, scenario in self.scenarios.items():
            desc = self._get_scenario_description(name)
            # Adiciona lista de parâmetros
            params = scenario.get_parameters()
            if params:
                param_desc = ", ".join(p.name for p in params)
                desc += "\n" + " "*27 + f" (parâmetros: {param_desc})"
            print(f"  {name:<25} - {desc}")

        print("  status                    - Verifica status da conexão")
        print("  help                      - Mostra esta ajuda")
        print("  quit                      - Encerra o programa")
        print("="*70)

    def _get_scenario_description(self, scenario_name: str) -> str:
        """Retorna descrição do cenário."""
        descriptions = {
            "min_cycle": "Authorize → Start → Meter → Stop",
            "failed_charging": "Authorize → Start → Meter → Failure → Stop"
        }
        return descriptions.get(scenario_name, "Authorize → Start → Meter → Stop")

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
            
    async def _get_parameters(self, scenario_name: str):
        """Coleta parâmetros do cenário interativamente."""
        scenario = self.scenarios[scenario_name]
        kwargs = {}

        params = scenario.get_parameters()
        if not params:
            return kwargs

        loop = asyncio.get_running_loop()

        for param in params:
            prompt = f"{param.name}"
            if param.description:
                prompt += f" ({param.description})"
            if param.default is not None:
                prompt += f" [{param.default}]"
            prompt += ": "

            # Solicita entrada do usuário de forma assíncrona
            value = await loop.run_in_executor(None, input, prompt)

            if value.strip() == "":
                value = None
            else:
                # Tenta converter para o tipo do valor padrão
                if param.default is not None and param.p_type is not None:
                    try:
                        if param.p_type == "int":
                            value = int(value)
                        elif param.p_type == "float":
                            value = float(value)
                        # Se for bool, talvez precise de um tratamento especial
                    except ValueError:
                        print(f"Valor inválido, usando padrão {param.default}")
                        value = param.default

            if value is None and param.required:
                print(f"Parâmetro {param.name} é obrigatório. Tente novamente.")
                # Opcional: recurse para repetir a pergunta (simplificado aqui)
                continue

            if value is not None: 
                kwargs[param.name] = value

        return kwargs

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
        if not state.registration:
            print("Posto não está registrado (BootNotification pendente).")
            return

        scenario = self.scenarios[scenario_name]

        # Determinar kwargs
        if args:
            # Mapeia argumentos posicionais para os parâmetros na ordem
            parameters = getattr(scenario, "parameters", [])
            kwargs = {}
            for i, arg in enumerate(args):
                if i < len(parameters):
                    param = parameters[i]
                    value = arg
                    if param.default is not None:
                        try:
                            if isinstance(param.default, int):
                                value = int(value)
                            elif isinstance(param.default, float):
                                value = float(value)
                        except ValueError:
                            print(f"Valor inválido para {param.name}, usando como string")
                    kwargs[param.name] = value
            # Preenche parâmetros não fornecidos com o valor padrão
            for param in parameters:
                if param.name not in kwargs:
                    kwargs[param.name] = param.default
        else:
            # Modo interativo
            kwargs = await self._get_parameters(scenario_name)

        self.transaction_counter += 1
        print("\n")
        print(f"-   Iniciando cenario #{scenario_name}!")
        try:
            success = await scenario.execute(self.cp, **kwargs)

            if success:
                print(f"-   Transação #{self.transaction_counter} concluída com sucesso!")
            else:
                print(f"-   Transação #{self.transaction_counter} falhou.")

        except Exception as e:
            logger.error(f" Erro na execução do cenário: {e}", exc_info=True)
            print(f" Erro durante execução: {e}")

        finally:
            print("\n" + "-"*70)

    async def _show_status(self):
        """Mostra status atual do sistema."""
        print(f"\nStatus do Sistema:")
        if self.cp:
            print(f"  Station ID: {self.cp.station_id}")
            print(f"  Qtd Conectores: {state.connectors_qty}")
            print(f"  Registrado: {'OK' if state.registration else 'X'}")
            #print(f"  Transação ativa: {self.cp._transaction_id if self.cp._transaction_id else 'Nenhuma'}")
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

    async def _cleanup(self):
        print("Handler de comandos encerrado.")